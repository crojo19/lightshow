import os
import gc
import machine
import urequests

class OTAUpdater:

    def __init__(self, github_repo, module='', main_dir='main', github_auth_token=None):
        self.github_repo = github_repo.rstrip('/').replace('https://github.com', 'https://api.github.com/repos')
        self.main_dir = main_dir
        self.module = module.rstrip('/')
        self.current_version = self._get_version(self.modulepath(self.main_dir))
        self.headers = None
        if github_auth_token is None:
            self.headers = {'User-Agent': 'Micropython'}
        else:
            token = "token " + github_auth_token
            self.headers = {'User-Agent': 'Micropython', 'Authorization': token}

    def get_current_version(self):
        return self.current_version

    def _get_version(self, directory, version_file_name='.version'):
        if version_file_name in os.listdir(directory):
            f = open(directory + '/' + version_file_name)
            version = f.read()
            f.close()
            return version
        return '0.0.0'

    def get_latest_version(self):
        latest_release = urequests.get(self.github_repo + '/releases/latest', headers=self.headers)
        version = latest_release.json()['tag_name']
        latest_release.close()
        return version

    def set_version_on_reboot(self, version):
        try:
            os.mkdir(self.modulepath('next'))
        except:
            pass
        with open(self.modulepath('next/.version_on_reboot'), 'w') as versionfile:
            versionfile.write(version)
            versionfile.close()

    def check_for_update(self):
        current_version = self.current_version
        latest_version = self.get_latest_version()
        if latest_version == self.current_version:
            return False, current_version, latest_version
        if latest_version == self.get_largest_version_number([current_version, latest_version]):
            print('New version available')
            return True, current_version, latest_version
        return False, current_version, latest_version

    def get_largest_version_number(self, versions=[]):
        return max(versions, key=self.version_split)

    def version_split(self, version):
        major, minor, micro = version.split('.')
        return int(major), int(minor), int(micro)

    def update_software(self):
        try:
            if 'next' in os.listdir(self.module):
                if '.version_on_reboot' in os.listdir(self.modulepath('next')):
                    latest_version = self._get_version(self.modulepath('next'), '.version_on_reboot')
                    print('New update found: ', latest_version)
                    self._download_and_update_software(latest_version)
            else:
                print('No new updates found...')
        except Exception as e:
            print(e)
            machine.reset()

    def _download_and_update_software(self, version):
        self.download_all_files(self.github_repo + '/contents/' + self.main_dir, version, self.github_repo + '/contents/')
        self.rmtree(self.modulepath(self.main_dir))
        os.rename(self.modulepath('next/.version_on_reboot'), self.modulepath('next/.version'))
        os.rename(self.modulepath('next'), self.modulepath(self.main_dir))
        os.remove("main.py")
        os.rename("main/main.py", "main.py")
        print('Update installed (', version, '), will reboot now')
        machine.reset()

    def rmtree(self, directory):
        for entry in os.ilistdir(directory):
            is_dir = entry[1] == 0x4000
            if is_dir:
                self.rmtree(directory + '/' + entry[0])
            else:
                os.remove(directory + '/' + entry[0])
        os.rmdir(directory)

    def download_all_files(self, root_url, version, other_url):
        file_list = urequests.get(root_url + '?ref=refs/tags/' + version, headers=self.headers)
        for file in file_list.json():
            if file['type'] == 'file':
                download_url = file['download_url']
                download_path = self.modulepath('next/' + file['path'].replace(self.main_dir + '/', ''))
                self.download_file(download_url.replace('refs/tags/', ''), download_path)
            elif file['type'] == 'dir':
                path = self.modulepath('next/' + file['path'].replace(self.main_dir + '/', ''))
                try:
                    os.mkdir(path)
                except:
                    pass
                self.download_all_files(root_url + '/' + file['name'], version, None)
        file_list.close()
        gc.collect()
        if other_url is not None:
            file_list = urequests.get(other_url + '?ref=refs/tags/' + version, headers=self.headers)
            for file in file_list.json():
                if file['name'] == 'main.py':
                    download_url = file['download_url']
                    download_path = self.modulepath('next/' + file['path'].replace(self.main_dir + '/', ''))
                    self.download_file(download_url.replace('refs/tags/', ''), download_path)
            file_list.close()
            gc.collect()

    def download_file(self, url, path):
        print('\tDownloading: ', path)
        try:
            os.remove(path)
        except:
            pass
        with open(path, 'w') as outfile:
            try:
                response = urequests.get(url, headers=self.headers)
                outfile.write(response.text)
            finally:
                response.close()
                outfile.close()
                gc.collect()

    def modulepath(self, path):
        return self.module + '/' + path if self.module else path
