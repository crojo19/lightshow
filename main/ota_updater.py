import usocket, os, gc, time

# Constants for memory-efficient chunk operations
CHUNK_SIZE = 2048  # Optimized for ESP32-S3
_RENAME_SUPPORTED = None  # Cache for rename capability test

class Response:

    def __init__(self, socket, saveToFile=None):
        self._socket = socket
        self._saveToFile = saveToFile
        self._encoding = 'utf-8'
        if saveToFile is not None:
            with open(saveToFile, 'wb') as outfile:
                data = self._socket.read(CHUNK_SIZE)
                while data:
                    outfile.write(data)
                    data = self._socket.read(CHUNK_SIZE)
                    gc.collect()  # Free memory during large downloads

            self.close()

    def close(self):
        if self._socket:
            self._socket.close()
            self._socket = None

    @property
    def content(self):
        if self._saveToFile is not None:
            raise SystemError('You cannot get the content from the response as you decided to save it in {}'.format(self._saveToFile))

        try:
            result = self._socket.read()
            return result
        finally:
            self.close()

    @property
    def text(self):
        return str(self.content, self._encoding)

    def json(self):
        try:
            import ujson
            result = ujson.load(self._socket)
            return result
        finally:
            self.close()


class HttpClient:

    def __init__(self, headers=None):
        self._headers = headers or {}

    @staticmethod
    def is_chunked_data(data):
        return getattr(data, "__iter__", None) and not getattr(data, "__len__", None)

    def request(self, method, url, data=None, json=None, file=None, custom=None, saveToFile=None, headers=None, stream=None):
        headers = headers or {}
        chunked = data and self.is_chunked_data(data)
        redirect = None #redirection url, None means no redirection
        def _write_headers(sock, _headers):
            for k in _headers:
                sock.write(b'{}: {}\r\n'.format(k, _headers[k]))

        try:
            proto, dummy, host, path = url.split('/', 3)
        except ValueError:
            proto, dummy, host = url.split('/', 2)
            path = ''
        if proto == 'http:':
            port = 80
        elif proto == 'https:':
            try:
                import ussl
            except:
                import ssl as ussl
                pass
            port = 443
        else:
            raise ValueError('Unsupported protocol: ' + proto)

        if ':' in host:
            host, port = host.split(':', 1)
            port = int(port)

        ai = usocket.getaddrinfo(host, port, 0, usocket.SOCK_STREAM)
        if len(ai) < 1:
            raise ValueError('You are not connected to the internet...')
        ai = ai[0]

        s = usocket.socket(ai[0], ai[1], ai[2])
        try:
            s.connect(ai[-1])
            if proto == 'https:':
                gc.collect()
                s = ussl.wrap_socket(s, server_hostname=host)
            s.write(b'%s /%s HTTP/1.0\r\n' % (method, path))
            if not 'Host' in headers:
                s.write(b'Host: %s\r\n' % host)
            # Iterate over keys to avoid tuple alloc
            _write_headers(s, self._headers)
            _write_headers(s, headers)

            # add user agent
            s.write(b'User-Agent: MicroPython Client\r\n')
            if json is not None:
                assert data is None
                import ujson
                data = ujson.dumps(json)
                s.write(b'Content-Type: application/json\r\n')

            if data:
                if chunked:
                    s.write(b"Transfer-Encoding: chunked\r\n")
                else:
                    s.write(b"Content-Length: %d\r\n" % len(data))
            s.write(b"\r\n")
            if data:
                if chunked:
                    for chunk in data:
                        s.write(b"%x\r\n" % len(chunk))
                        s.write(chunk)
                        s.write(b"\r\n")
                    s.write(b"0\r\n\r\n")
                else:
                    s.write(data)
            elif file:
                s.write(b'Content-Length: %d\r\n' % os.stat(file)[6])
                s.write(b'\r\n')
                with open(file, 'rb') as file_object:
                    while True:
                        chunk = file_object.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        s.write(chunk)
            elif custom:
                custom(s)
            else:
                s.write(b'\r\n')

            l = s.readline()
            #print('l: ', l)
            l = l.split(None, 2)
            status = int(l[1])
            reason = ''
            if len(l) > 2:
                reason = l[2].rstrip()
            while True:
                l = s.readline()
                if not l or l == b'\r\n':
                    break
                #print('l: ', l)
                if l.startswith(b'Transfer-Encoding:'):
                    if b'chunked' in l:
                        raise ValueError('Unsupported ' + l)
                elif l.startswith(b'Location:') and not 200 <= status <= 299:
                    if status in [301, 302, 303, 307, 308]:
                        redirect = l[10:-2].decode()
                    else:
                        raise NotImplementedError("Redirect {} not yet supported".format(status))
        except OSError:
            s.close()
            raise

        if redirect:
            s.close()
            # Fix: pass all original kwargs on redirect
            kw = {'data': data, 'json': json, 'file': file, 'custom': custom,
                  'saveToFile': saveToFile, 'headers': headers, 'stream': stream}
            if status in [301, 302, 303]:
                return self.request('GET', url=redirect, **kw)
            else:
                return self.request(method, redirect, **kw)
        else:
            resp = Response(s, saveToFile)
            resp.status_code = status
            resp.reason = reason
            gc.collect()
            return resp

    def head(self, url, **kw):
        return self.request('HEAD', url, **kw)

    def get(self, url, **kw):
        return self.request('GET', url, **kw)

    def post(self, url, **kw):
        return self.request('POST', url, **kw)

    def put(self, url, **kw):
        return self.request('PUT', url, **kw)

    def patch(self, url, **kw):
        return self.request('PATCH', url, **kw)

    def delete(self, url, **kw):
        return self.request('DELETE', url, **kw)

class OTAUpdater:
    """
    A class to update your MicroController with the latest version from a GitHub tagged release,
    optimized for low power usage.
    """

    def __init__(self, github_repo, github_src_dir='', module='', main_dir='main', new_version_dir='next', secrets_file=None, github_auth_token=None):
        headers = {'User-Agent': 'Micropython'}
        if github_auth_token:
            headers['Authorization'] = "token " + github_auth_token
        self.http_client = HttpClient(headers=headers)
        self.github_repo = github_repo.rstrip('/').replace('https://github.com/', '')
        self.github_src_dir = '' if not github_src_dir else github_src_dir.rstrip('/') + '/'
        self.module = module.rstrip('/')
        self.main_dir = main_dir
        self.new_version_dir = new_version_dir
        self.secrets_file = secrets_file
        self.current_version = self.get_version(self.modulepath(self.main_dir))

    def get_current_version(self):
        return self.current_version

    def update_software(self):
        return self.install_update_if_available()

    def check_for_update_to_install_during_next_reboot(self) -> bool:
        """Function which will check the GitHub repo if there is a newer version available.

        This method expects an active internet connection and will compare the current
        version with the latest version available on GitHub.
        If a newer version is available, the file 'next/.version' will be created
        and you need to call machine.reset(). A reset is needed as the installation process
        takes up a lot of memory (mostly due to the http stack)

        Returns
        -------
            bool: true if a new version is available, false otherwise
        """

        (current_version, latest_version) = self._check_for_new_version()
        if latest_version > current_version:
            print('New version available, will download and install on next reboot')
            self._create_new_version_file(latest_version)
            return True

        return False

    def install_update_if_available_after_boot(self, ssid, password) -> bool:
        """This method will install the latest version if out-of-date after boot.

        This method, which should be called first thing after booting, will check if the
        next/.version' file exists.

        - If yes, it initializes the WIFI connection, downloads the latest version and installs it
        - If no, the WIFI connection is not initialized as no new known version is available
        """

        try:
            version_files = os.listdir(self.modulepath(self.new_version_dir))
            if '.version' in version_files:
                latest_version = self.get_version(self.modulepath(self.new_version_dir), '.version')
                print('New update found: ', latest_version)
                OTAUpdater._using_network(ssid, password)
                self.install_update_if_available()
                return True
        except OSError:
            pass

        print('No new updates found...')
        return False

    def install_update_if_available(self) -> bool:
        """This method will immediately install the latest version if out-of-date.

        This method expects an active internet connection and allows you to decide yourself
        if you want to install the latest version. It is necessary to run it directly after boot
        (for memory reasons) and you need to restart the microcontroller if a new version is found.

        Returns
        -------
            bool: true if a new version is available, false otherwise
        """

        (current_version, latest_version) = self._check_for_new_version()
        if latest_version > current_version:
            print('Updating to version {}...'.format(latest_version))
            self._create_new_version_file(latest_version)
            self._download_new_version(latest_version)
            self._copy_secrets_file()
            self._delete_old_version()
            self._install_new_version()
            return True

        return False


    @staticmethod
    def _using_network(ssid, password, timeout_ms=30000):
        import network
        sta_if = network.WLAN(network.STA_IF)
        if not sta_if.isconnected():
            print('connecting to network...')
            sta_if.active(True)
            sta_if.connect(ssid, password)
            # Sleep instead of busy-wait to save CPU, with timeout
            elapsed = 0
            while not sta_if.isconnected() and elapsed < timeout_ms:
                time.sleep_ms(100)
                elapsed += 100
            if not sta_if.isconnected():
                raise OSError('Failed to connect to WiFi after {}ms'.format(timeout_ms))
        print('network config:', sta_if.ifconfig())

    def _check_for_new_version(self):
        current_version = self.get_version(self.modulepath(self.main_dir))
        latest_version = self.get_latest_version()

        print('Checking version... ')
        print('\tCurrent version: ', current_version)
        print('\tLatest version: ', latest_version)
        return (current_version, latest_version)

    def _create_new_version_file(self, latest_version):
        self.mkdir(self.modulepath(self.new_version_dir))
        with open(self.modulepath(self.new_version_dir + '/.version'), 'w') as versionfile:
            versionfile.write(latest_version)

    def get_version(self, directory, version_file_name='.version'):
        try:
            with open(directory + '/' + version_file_name) as f:
                return f.read().strip()
        except OSError:
            return '0.0'

    def get_latest_version(self):
        latest_release = self.http_client.get('https://api.github.com/repos/{}/releases/latest'.format(self.github_repo))
        gh_json = latest_release.json()
        try:
            version = gh_json['tag_name']
        except KeyError as e:
            raise ValueError(
                "Release not found: \n",
                "Please ensure release as marked as 'latest', rather than pre-release \n",
                "github api message: \n {} \n ".format(gh_json)
            )
        latest_release.close()
        gc.collect()
        return version

    def get_largest_version_number(self, versions=[]):
        return max(versions, key=self.version_split)

    def version_split(self, version):
        major, minor, micro = version.split('.')
        return int(major), int(minor), int(micro)

    def check_for_update(self):
        current_version = self.current_version
        latest_version = self.get_latest_version()
        if latest_version == self.current_version:
            return False, current_version, latest_version
        if latest_version == self.get_largest_version_number([current_version, latest_version]):
            print('New version available')
            return True, current_version, latest_version
        return False, current_version, latest_version

    def _download_new_version(self, version):
        print('Downloading version {}'.format(version))
        self._download_all_files(version)
        print('Version {} downloaded to {}'.format(version, self.modulepath(self.new_version_dir)))

    def _download_all_files(self, version, sub_dir=''):
        url = 'https://api.github.com/repos/{}/contents/{}{}{}?ref=refs/tags/{}'.format(self.github_repo, self.github_src_dir, self.main_dir, sub_dir, version)
        gc.collect()
        file_list = self.http_client.get(url)
        file_list_json = file_list.json()
        for file in file_list_json:
            path = self.modulepath(self.new_version_dir + '/' + file['path'].replace(self.main_dir + '/', '').replace(self.github_src_dir, ''))
            if file['type'] == 'file':
                gitPath = file['path']
                print('\tDownloading: ', gitPath, 'to', path)
                self._download_file(version, gitPath, path)
            elif file['type'] == 'dir':
                print('Creating dir', path)
                self.mkdir(path)
                self._download_all_files(version, sub_dir + '/' + file['name'])
            gc.collect()

        file_list.close()

    def _download_file(self, version, gitPath, path):
        self.http_client.get('https://raw.githubusercontent.com/{}/{}/{}'.format(self.github_repo, version, gitPath), saveToFile=path)
        gc.collect()

    def _copy_secrets_file(self):
        if self.secrets_file:
            fromPath = self.modulepath(self.main_dir + '/' + self.secrets_file)
            toPath = self.modulepath(self.new_version_dir + '/' + self.secrets_file)
            print('Copying secrets file from {} to {}'.format(fromPath, toPath))
            self._copy_file(fromPath, toPath)
            print('Copied secrets file from {} to {}'.format(fromPath, toPath))

    def _delete_old_version(self):
        print('Deleting old version at {} ...'.format(self.modulepath(self.main_dir)))
        self._rmtree(self.modulepath(self.main_dir))
        print('Deleted old version at {} ...'.format(self.modulepath(self.main_dir)))

    def _install_new_version(self):
        print('Installing new version at {} ...'.format(self.modulepath(self.main_dir)))
        if self._os_supports_rename():
            os.rename(self.modulepath(self.new_version_dir), self.modulepath(self.main_dir))
        else:
            self._copy_directory(self.modulepath(self.new_version_dir), self.modulepath(self.main_dir))
            self._rmtree(self.modulepath(self.new_version_dir))
        print('Update installed, please reboot now')

    def _rmtree(self, directory):
        for entry in os.ilistdir(directory):
            is_dir = entry[1] == 0x4000
            if is_dir:
                self._rmtree(directory + '/' + entry[0])
            else:
                os.remove(directory + '/' + entry[0])
        os.rmdir(directory)

    def _os_supports_rename(self) -> bool:
        global _RENAME_SUPPORTED
        if _RENAME_SUPPORTED is not None:
            return _RENAME_SUPPORTED

        try:
            self._mk_dirs('otaUpdater/osRenameTest')
            os.rename('otaUpdater', 'otaUpdated')
            result = len(os.listdir('otaUpdated')) > 0
            self._rmtree('otaUpdated')
            _RENAME_SUPPORTED = result
            return result
        except (OSError, Exception):
            _RENAME_SUPPORTED = False
            return False

    def _copy_directory(self, fromPath, toPath):
        if not self._exists_dir(toPath):
            self._mk_dirs(toPath)

        for entry in os.ilistdir(fromPath):
            is_dir = entry[1] == 0x4000
            if is_dir:
                self._copy_directory(fromPath + '/' + entry[0], toPath + '/' + entry[0])
            else:
                self._copy_file(fromPath + '/' + entry[0], toPath + '/' + entry[0])

    def _copy_file(self, fromPath, toPath):
        with open(fromPath, 'rb') as fromFile:
            with open(toPath, 'wb') as toFile:
                while True:
                    data = fromFile.read(CHUNK_SIZE)
                    if not data:
                        break
                    toFile.write(data)

    def _exists_dir(self, path) -> bool:
        try:
            os.listdir(path)
            return True
        except OSError:
            return False

    def _mk_dirs(self, path:str):
        paths = path.split('/')
        pathToCreate = []
        for x in paths:
            pathToCreate.append(x)
            self.mkdir('/'.join(pathToCreate))

    # different micropython versions act differently when directory already exists
    def mkdir(self, path:str):
        try:
            os.mkdir(path)
        except OSError as exc:
            if exc.args[0] == 17:
                pass


    def modulepath(self, path):
        return self.module + '/' + path if self.module else path
