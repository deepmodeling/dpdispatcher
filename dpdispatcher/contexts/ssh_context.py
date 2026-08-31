#!/usr/bin/env python

"""Provide SSH command execution and rsync/SFTP file staging."""

from __future__ import annotations

import errno
import os
import pathlib
import posixpath
import shlex
import shutil
import socket
import tarfile
import time
import uuid
from functools import cache
from stat import S_ISDIR, S_ISREG
from typing import TYPE_CHECKING, Any

import paramiko
import paramiko.ssh_exception
from dargs.dargs import Argument

from dpdispatcher.base_context import BaseContext
from dpdispatcher.dlog import dlog
from dpdispatcher.file_manager import (
    AtomicTextWriter,
    PathResolver,
    RemoteManifestBuilder,
    SubmissionStagingPlan,
)
from dpdispatcher.utils.archive import safe_extract_tar

# from dpdispatcher.submission import Machine
from dpdispatcher.utils.utils import (
    RetrySignal,
    generate_totp,
    get_sha256,
    retry,
    rsync,
)

if TYPE_CHECKING:
    from dpdispatcher.submission import Submission


class SSHSession:
    """Manage a resilient Paramiko SSH connection and file-transfer helpers."""

    def __init__(
        self,
        hostname: str,
        username: str,
        password: str | None = None,
        port: int = 22,
        key_filename: str | None = None,
        passphrase: str | None = None,
        timeout: int = 10,
        totp_secret: str | None = None,
        tar_compress: bool = True,
        look_for_keys: bool = True,
        execute_command: str | None = None,
        proxy_command: str | None = None,
        archive_chunk_size: int = 0,
    ) -> None:
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self.key_filename = key_filename
        self.passphrase = passphrase
        self.timeout = timeout
        self.totp_secret = totp_secret
        self.ssh = None
        self.tar_compress = tar_compress
        if archive_chunk_size < 0:
            raise ValueError("archive_chunk_size must be greater than or equal to 0")
        self.archive_chunk_size = archive_chunk_size
        self.look_for_keys = look_for_keys
        self.execute_command = execute_command
        self.proxy_command = proxy_command
        self._keyboard_interactive_auth = False
        self._setup_ssh()

    # @classmethod
    # def deserialize(cls, jdata):
    #     instance = cls(**jdata)
    #     return instance

    # def bk_ensure_alive(self,
    #                  max_check = 10,
    #                  sleep_time = 10):
    #     count = 1
    #     while not self._check_alive():
    #         if count == max_check:
    #             raise RuntimeError('cannot connect ssh after %d failures at interval %d s' %
    #                                (max_check, sleep_time))
    #         dlog.info('connection check failed, try to reconnect to ' + self.remote_host)
    #         self._setup_ssh(hostname=self.remote_host,
    #                         port=self.remote_port,
    #                         username=self.remote_uname,
    #                         password=self.remote_password,
    #                         key_filename=self.local_key_filename,
    #                         timeout=self.remote_timeout,
    #                         passphrase=self.local_key_passphrase)
    #         count += 1
    #         time.sleep(sleep_time)

    def ensure_alive(self, max_check: int = 10, sleep_time: int = 10) -> None:
        count = 1
        while not self._check_alive():
            if count == max_check:
                raise RuntimeError(
                    f"cannot connect ssh after {max_check} failures at interval {sleep_time} s"
                )
            dlog.info("connection check failed, try to reconnect to " + self.hostname)
            self._setup_ssh()
            count += 1
            time.sleep(sleep_time)

    def _check_alive(self) -> bool | None:
        if self.ssh is None:
            return False
        try:
            transport = self.ssh.get_transport()
            if transport is None or not transport.is_active():
                return False
            transport.send_ignore()
            # Paramiko silently drops ``send_ignore`` when a transport dies
            # between the initial check and the probe. Verify the state again
            # so ``ensure_alive`` reconnects before the next SSH operation.
            return transport.is_active()
        except (EOFError, OSError, paramiko.ssh_exception.SSHException):
            return False

    # def bk_setup_ssh(self,
    #                hostname,
    #                port=22,
    #                username=None,
    #                password=None,
    #                key_filename=None,
    #                timeout=None,
    #                passphrase=None):
    #     self.ssh = paramiko.SSHClient()
    #     # ssh_client.load_system_host_keys()
    #     self.ssh.set_missing_host_key_policy(paramiko.WarningPolicy)
    #     self.ssh.connect(hostname=hostname, port=port,
    #                      username=username, password=password,
    #                      key_filename=key_filename, timeout=timeout, passphrase=passphrase)
    #     assert(self.ssh.get_transport().is_active())
    #     transport = self.ssh.get_transport()
    #     transport.set_keepalive(60)

    @retry(max_retry=6, sleep=1)
    def _setup_ssh(self) -> None:
        # machine = self.machine
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy)
        # if self.totp_secret and self.password is None:
        #     self.password = generate_totp(self.totp_secret)
        # self.ssh.connect(hostname=self.hostname, port=self.port,
        #                 username=self.username, password=self.password,
        #                 key_filename=self.key_filename, timeout=self.timeout,passphrase=self.passphrase,
        #                 compress=True,
        #                 )
        # assert(self.ssh.get_transport().is_active())
        # transport = self.ssh.get_transport()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)

        # Use ProxyCommand if configured (either directly or via jump host parameters)
        if self.proxy_command is not None:
            sock = paramiko.ProxyCommand(self.proxy_command)
        else:
            sock.connect((self.hostname, self.port))

        # Make a Paramiko Transport object using the socket
        ts = paramiko.Transport(sock)
        ts.banner_timeout = 60
        ts.auth_timeout = self.timeout + 20
        ts.use_compression(compress=True)

        # Tell Paramiko that the Transport is going to be used as a client
        ts.start_client(timeout=self.timeout)

        # Begin authentication; note that the username and callback are passed
        key = None
        key_ok = False
        key_error = None
        keyfiles = []
        if self.key_filename:
            key_path = os.path.abspath(self.key_filename)
            if os.path.exists(key_path):
                for pkey_class in (
                    paramiko.RSAKey,
                    paramiko.ECDSAKey,
                    paramiko.Ed25519Key,
                ):
                    try:
                        # passing empty passphrase would not raise error.
                        key = pkey_class.from_private_key_file(
                            key_path, self.passphrase
                        )
                    except paramiko.SSHException:
                        pass
                    if key is not None:
                        break
            else:
                raise OSError(f"{key_path} not found!")
        elif self.look_for_keys:
            for keytype, name in [
                (paramiko.RSAKey, "rsa"),
                (paramiko.ECDSAKey, "ecdsa"),
                (paramiko.Ed25519Key, "ed25519"),
            ]:
                for directory in [".ssh", "ssh"]:
                    full_path = os.path.join(
                        os.path.expanduser("~"), directory, f"id_{name}"
                    )
                    if os.path.isfile(full_path):
                        keyfiles.append((keytype, full_path))
                        # TODO: supporting cert
            for pkey_class, filename in keyfiles:
                try:
                    key = pkey_class.from_private_key_file(filename, self.passphrase)
                except paramiko.SSHException:
                    pass
                if key is not None:
                    break

        allowed_types = set()
        if key is not None:
            try:
                allowed_types = set(ts.auth_publickey(self.username, key))
            except paramiko.ssh_exception.AuthenticationException as e:
                key_error = e
            else:
                key_ok = True
        if self.totp_secret is not None or "keyboard-interactive" in allowed_types:
            try:
                ts.auth_interactive(self.username, self.inter_handler)
            except paramiko.ssh_exception.AuthenticationException:
                # since the asynchrony of interactive authentication, one addtional try is added
                # retry for up to 6 times
                raise RetrySignal("Authentication failed")
            self._keyboard_interactive_auth = True
        elif key_ok:
            pass
        elif self.password is not None:
            ts.auth_password(self.username, self.password)
        elif key_error is not None:
            raise RuntimeError(
                "Authentication failed, try to provide password"
            ) from key_error
        else:
            raise RuntimeError("Please provide at least one form of authentication")
        assert ts.is_active()
        # Opening a session creates a channel along the socket to the server
        try:
            ts.open_session(timeout=self.timeout)
        except paramiko.ssh_exception.SSHException:
            # retry for up to 6 times
            # ref: https://github.com/paramiko/paramiko/issues/1508
            raise RetrySignal("Opening session failed")
        ts.set_keepalive(60)
        self.ssh._transport = ts
        # reset sftp
        self._sftp = None
        if self.execute_command is not None:
            self.exec_command(self.execute_command)

    def inter_handler(
        self, title: str, instructions: str, prompt_list: list[tuple[str, bool]]
    ) -> list[str]:
        """inter_handler: the callback for paramiko.transport.auth_interactive.

        The prototype for this function is defined by Paramiko, so all of the
        arguments need to be there, even though we don't use 'title' or
        'instructions'.

        The function is expected to return a tuple of data containing the
        responses to the provided prompts. Experimental results suggests that
        there will be one call of this function per prompt, but the mechanism
        allows for multiple prompts to be sent at once, so it's best to assume
        that that can happen.

        Since tuples can't really be built on the fly, the responses are
        collected in a list which is then converted to a tuple when it's time
        to return a value.

        Experiments suggest that the username prompt never happens. This makes
        sense, but the Username prompt is included here just in case.
        """
        resp = []  # Initialize the response container

        # Walk the list of prompts that the server sent that we need to answer
        for pr in prompt_list:
            # str() used to to make sure that we're dealing with a string rather than a unicode string
            # strip() used to get rid of any padding spaces sent by the server
            pr_str = str(pr[0]).strip().lower()
            if "username" in pr_str:
                resp.append(self.username)
            elif "password" in pr_str:
                resp.append(self.password)
            elif (
                "verification" in pr_str
                or "token" in pr_str
                and self.totp_secret is not None
            ):
                assert self.totp_secret is not None
                resp.append(generate_totp(self.totp_secret))

        return resp

    def get_ssh_client(self) -> paramiko.SSHClient:
        assert self.ssh is not None
        return self.ssh

    # def get_session_root(self):
    #     return self.remote_root

    def close(self) -> None:
        assert self.ssh is not None
        self.ssh.close()

    @retry(sleep=1)
    def exec_command(self, cmd: str) -> tuple[Any, Any, Any]:  # noqa: ANN401
        """Call ``SSHClient.exec_command`` with connection checks and retries."""
        assert self.ssh is not None
        try:
            return self.ssh.exec_command(cmd)
        except (TimeoutError, paramiko.ssh_exception.SSHException, EOFError) as e:
            # SSH session not active
            # retry for up to 3 times
            # ensure alive
            self.ensure_alive()
            raise RetrySignal(f"SSH session not active in calling {cmd}") from e

    @property
    def sftp(self) -> paramiko.SFTPClient:
        """Returns sftp. Open a new one if not existing."""
        if self._sftp is None:
            assert self.ssh is not None
            self.ensure_alive()
            self._sftp = self.ssh.open_sftp()
        return self._sftp

    @staticmethod
    def arginfo() -> Argument:
        doc_hostname = "Hostname or IP address of the SSH target machine."
        doc_username = "Username used to log in to the target system."
        doc_password = (
            "(deprecated) password of linux system. Please use "
            "`SSH keys <https://www.ssh.com/academy/ssh/key>`_ instead to improve security."
        )
        doc_port = "SSH port of the target machine. Usually 22."
        doc_key_filename = (
            "Path to the private key file used for SSH authentication. If left None, DPDispatcher can "
            "try discoverable keys in ~/.ssh or fall back to password-based login if configured."
        )
        doc_passphrase = "Passphrase for the SSH private key, if the key is encrypted."
        doc_timeout = "Timeout in seconds for establishing the SSH connection."
        doc_totp_secret = "Time-based one-time-password secret used for keyboard-interactive 2FA. It should be a base32-encoded string."
        doc_tar_compress = "Whether upload/download tar archives are compressed. Keeping this True usually reduces transfer size at the cost of extra CPU time."
        doc_archive_chunk_size = (
            "Maximum size in bytes of each temporary archive part when downloading "
            "backward files. The default 0 transfers one archive as before. A positive "
            "value requires the remote `split` command and bounds each individual transfer."
        )
        doc_look_for_keys = "Whether to search for discoverable private key files in ~/.ssh when key_filename is not provided."
        doc_execute_command = "Optional command executed immediately after the SSH connection is established."
        doc_proxy_command = "Optional SSH ProxyCommand used to reach the target through an intermediate host or tunnel."
        ssh_remote_profile_args = [
            Argument("hostname", str, optional=False, doc=doc_hostname),
            Argument("username", str, optional=False, doc=doc_username),
            Argument("password", str, optional=True, doc=doc_password),
            Argument("port", int, optional=True, default=22, doc=doc_port),
            Argument(
                "key_filename",
                [str, type(None)],
                optional=True,
                default=None,
                doc=doc_key_filename,
            ),
            Argument(
                "passphrase",
                [str, type(None)],
                optional=True,
                default=None,
                doc=doc_passphrase,
            ),
            Argument("timeout", int, optional=True, default=10, doc=doc_timeout),
            Argument(
                "totp_secret",
                str,
                optional=True,
                default=None,
                doc=doc_totp_secret,
            ),
            Argument(
                "tar_compress",
                bool,
                optional=True,
                default=True,
                doc=doc_tar_compress,
            ),
            Argument(
                "look_for_keys",
                bool,
                optional=True,
                default=True,
                doc=doc_look_for_keys,
            ),
            Argument(
                "execute_command",
                str,
                optional=True,
                default=None,
                doc=doc_execute_command,
            ),
            Argument(
                "proxy_command",
                [str, type(None)],
                optional=True,
                default=None,
                doc=doc_proxy_command,
            ),
            Argument(
                "archive_chunk_size",
                int,
                optional=True,
                doc=doc_archive_chunk_size,
            ),
        ]
        ssh_remote_profile_format = Argument(
            "ssh_session", dict, ssh_remote_profile_args
        )
        return ssh_remote_profile_format

    def put(self, from_f: str, to_f: str) -> paramiko.SFTPAttributes | None:
        if self.rsync_available:
            # For rsync, we need to use %h:%p placeholders for target host/port
            proxy_cmd_rsync = None
            if self.proxy_command is not None:
                proxy_cmd_rsync = self.proxy_command.replace(
                    f"{self.hostname}:{self.port}", "%h:%p"
                )
            return rsync(
                from_f,
                self.remote + ":" + to_f,
                port=self.port,
                key_filename=self.key_filename,
                timeout=self.timeout,
                proxy_command=proxy_cmd_rsync,
            )
        return self.sftp.put(from_f, to_f)

    def get(self, from_f: str, to_f: str) -> paramiko.SFTPAttributes | None:
        if self.rsync_available:
            # For rsync, we need to use %h:%p placeholders for target host/port
            proxy_cmd_rsync = None
            if self.proxy_command is not None:
                proxy_cmd_rsync = self.proxy_command.replace(
                    f"{self.hostname}:{self.port}", "%h:%p"
                )
            return rsync(
                self.remote + ":" + from_f,
                to_f,
                port=self.port,
                key_filename=self.key_filename,
                timeout=self.timeout,
                proxy_command=proxy_cmd_rsync,
            )
        return self.sftp.get(from_f, to_f)

    @property
    @cache
    def rsync_available(self) -> bool:
        return (
            shutil.which("rsync") is not None
            and self.password is None
            and self.exec_command("rsync --version")[1].channel.recv_exit_status() == 0
            and self.totp_secret is None
            and self.passphrase is None
            and not self._keyboard_interactive_auth
        )

    @property
    def remote(self) -> str:
        return f"{self.username}@{self.hostname}"


class SSHContext(BaseContext):
    """Run submissions on a remote host reached through an SSH session."""

    def __init__(
        self,
        local_root: str,
        remote_root: str,
        remote_profile: dict[str, Any],  # noqa: ANN401
        clean_asynchronously: bool = False,
        create_remote_root: bool = False,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        assert isinstance(local_root, str)
        self.init_local_root = local_root
        self.init_remote_root = remote_root
        self.temp_local_root = os.path.abspath(local_root)
        assert os.path.isabs(os.path.realpath(remote_root)), (
            "remote_root must be a abspath"
        )
        self.temp_remote_root = remote_root
        # Keep the disabled chunking default out of serialized profiles so
        # pre-feature submissions retain their original identity/hash.
        self.remote_profile = dict(remote_profile)
        if self.remote_profile.get("archive_chunk_size") == 0:
            self.remote_profile.pop("archive_chunk_size")
        self.remote_root = ""
        # Set during bind_submission so recovery can undo a rename if a later
        # bind step fails.  Empty placeholder directories are not considered
        # migrated because they carry no completion state.
        self._last_recovery_moved = False
        # Distinguish a benign race (the source disappeared because another
        # process already moved it) from a hard conflict where both roots are
        # present.  Submission recovery uses this marker to decide which
        # locator remains retryable after a later bind failure.
        self._last_recovery_already_at_destination = False
        self._last_recovery_conflict = False

        # self.job_uuid = None
        self.clean_asynchronously = clean_asynchronously
        self.create_remote_root = create_remote_root
        # self.job_uuid = job_uuid
        # if job_uuid:
        #    self.job_uuid=job_uuid
        # else:
        #    self.job_uuid = str(uuid.uuid4())
        self.ssh_session = SSHSession(**self.remote_profile)
        # self.temp_remote_root = os.path.join(self.ssh_session.get_session_root())
        self.ssh_session.ensure_alive()
        self._mkdir(self.temp_remote_root, recursive=self.create_remote_root)

    @classmethod
    def load_from_dict(cls, context_dict: dict[str, Any]) -> SSHContext:  # noqa: ANN401
        # instance = cls()
        # input = dict(
        #     hostname = jdata['hostname'],
        #     remote_root = jdata['remote_root'],
        #     username = jdata['username'],
        #     password = jdata.get('password', None),
        #     port = jdata.get('port', 22),
        #     key_filename = jdata.get('key_filename', None),
        #     passphrase = jdata.get('passphrase', None),
        #     timeout = jdata.get('timeout', 10),
        #     tar_compress = jdata.get('tar_compress', True)
        # )
        local_root = context_dict["local_root"]
        remote_root = context_dict["remote_root"]
        remote_profile = context_dict["remote_profile"]
        clean_asynchronously = context_dict.get("clean_asynchronously", False)
        create_remote_root = context_dict.get("create_remote_root", False)

        ssh_context = cls(
            local_root=local_root,
            remote_root=remote_root,
            remote_profile=remote_profile,
            clean_asynchronously=clean_asynchronously,
            create_remote_root=create_remote_root,
        )
        # local_root = jdata['local_root']
        # ssh_session = SSHSession(**input)
        # ssh_context = SSHContext(
        #     local_root=local_root,
        #     ssh_session=ssh_session,
        #     clean_asynchronously=jdata.get('clean_asynchronously', False),
        #     )
        return ssh_context

    @property
    def ssh(self) -> paramiko.SSHClient:
        return self.ssh_session.get_ssh_client()

    @property
    def sftp(self) -> paramiko.SFTPClient:
        return self.ssh_session.sftp

    def close(self) -> None:
        self.ssh_session.close()

    def get_job_root(self) -> str:
        return self.remote_root

    @staticmethod
    def _is_missing_remote_path(error: OSError) -> bool:
        """Return whether an SFTP error reports a missing remote path."""
        return isinstance(error, FileNotFoundError) or error.errno == errno.ENOENT

    def _recover_remote_root(self, old_remote_root: str) -> bool:
        """Move recoverable state from a previous submission hash.

        An empty directory can be left behind when a submission is rebound before
        any files are uploaded. It is only a placeholder, so remove it instead of
        moving it to the new hash. Non-empty directories contain recovery state
        and are renamed only when the destination does not already exist.
        """
        assert self.remote_root is not None
        sftp = self.sftp

        try:
            old_entries = sftp.listdir(old_remote_root)
        except OSError as error:
            if self._is_missing_remote_path(error):
                # A concurrent recovery may have moved the source before this
                # process listed it.  If the destination now exists, preserve
                # that destination as the authoritative state.
                try:
                    sftp.stat(self.remote_root)
                except OSError as destination_error:
                    if not self._is_missing_remote_path(destination_error):
                        raise
                else:
                    self._last_recovery_already_at_destination = True
                return False
            raise

        if not old_entries:
            try:
                sftp.rmdir(old_remote_root)
            except OSError as error:
                # Another recovery may remove the same placeholder after listdir.
                # Other failures, including a newly non-empty directory, must surface.
                if not self._is_missing_remote_path(error):
                    raise
            return False

        try:
            sftp.stat(self.remote_root)
        except OSError as error:
            if not self._is_missing_remote_path(error):
                raise
        else:
            # Never overwrite a destination that may contain newer recovery data.
            # Surface the conflict instead of silently abandoning completion
            # tags that remain in the old root.
            raise FileExistsError(
                "Cannot migrate recovered SSH submission: both old and new "
                f"roots exist ({old_remote_root}, {self.remote_root})"
            )

        try:
            # Unlike a shell `mv`, SFTP rename exposes a missing-source errno. This
            # makes rebinding idempotent when another process wins the same race.
            sftp.rename(old_remote_root, self.remote_root)
        except OSError as error:
            if not self._is_missing_remote_path(error):
                raise
            # Treat a lost-source race as an already-completed move only when
            # the destination is observable.  Otherwise the caller can safely
            # restore the original locator and retry.
            try:
                sftp.stat(self.remote_root)
            except OSError as destination_error:
                if not self._is_missing_remote_path(destination_error):
                    raise
            else:
                self._last_recovery_already_at_destination = True
            return False
        return True

    def _mkdir(self, remote_dir: str, recursive: bool = False) -> None:
        if not remote_dir:
            return

        sftp = self.sftp
        if not recursive:
            try:
                sftp.mkdir(remote_dir)
            except OSError as mkdir_error:
                # SFTP does not expose an atomic mkdir-if-absent operation.
                # Ignore the failure only when the requested path is already
                # a directory; permission and path-type errors must surface.
                try:
                    existing = sftp.stat(remote_dir)
                except OSError:
                    raise mkdir_error
                existing_mode = existing.st_mode
                if existing_mode is None or not S_ISDIR(existing_mode):
                    raise mkdir_error
            return

        path = pathlib.PurePosixPath(remote_dir)
        current = path.root if path.is_absolute() else ""
        parts = path.parts[1:] if path.is_absolute() else path.parts
        for part in parts:
            current = pathlib.PurePosixPath(current, part).as_posix()
            try:
                sftp.mkdir(current)
            except OSError as mkdir_error:
                try:
                    existing = sftp.stat(current)
                except OSError:
                    raise mkdir_error
                existing_mode = existing.st_mode
                if existing_mode is None or not S_ISDIR(existing_mode):
                    raise mkdir_error

    def bind_submission(self, submission: Submission) -> None:
        assert self.ssh_session is not None
        assert self.ssh_session.ssh is not None
        self.submission = submission
        assert submission.submission_hash is not None
        self.local_root = pathlib.PurePath(
            os.path.join(self.temp_local_root, submission.work_base)
        ).as_posix()
        old_remote_root = self.remote_root
        # self.remote_root = os.path.join(self.temp_remote_root, self.submission.submission_hash, self.submission.work_base )
        self.remote_root = pathlib.PurePath(
            os.path.join(self.temp_remote_root, submission.submission_hash)
        ).as_posix()
        self._last_recovery_moved = False
        self._last_recovery_conflict = False
        self._last_recovery_already_at_destination = False
        if old_remote_root and old_remote_root != self.remote_root:
            try:
                self._last_recovery_moved = self._recover_remote_root(old_remote_root)
            except FileExistsError:
                self._last_recovery_conflict = True
                raise

        self._mkdir(self.remote_root, recursive=self.create_remote_root)

        # self.job_uuid = submission.submission_hash
        # dlog.debug("debug:SSHContext.bind_submission"
        #     "{submission.submission_hash}; {self.local_root}; {self.remote_root")

        # try:
        # print('self.remote_root', self.remote_root)
        # sftp = self.ssh_session.ssh.open_sftp()
        # sftp.mkdir(self.remote_root)
        # sftp.close()
        # except Exception:
        #     pass

    def upload(
        self,
        # job_dirs,
        submission: Submission,
        # local_up_files,
        dereference: bool = True,
    ) -> None:
        assert self.remote_root is not None
        dlog.info(f"remote path: {self.remote_root}")
        # remote_cwd =
        self.ssh_session.sftp.chdir(self.temp_remote_root)
        recover = False
        try:
            self.ssh_session.sftp.mkdir(os.path.basename(self.remote_root))
        except OSError:
            # mkdir failed meaning it exists
            if len(self.ssh_session.sftp.listdir(os.path.basename(self.remote_root))):
                recover = True
        self.ssh_session.sftp.chdir(None)

        manifest = SubmissionStagingPlan(self.local_root, submission).upload_manifest()
        if manifest.missing:
            missing = manifest.missing[0]
            raise FileNotFoundError(
                "cannot find upload file "
                + os.path.join(
                    self.local_root, missing.destination_prefix, missing.pattern
                )
            )
        resolver = PathResolver(self.local_root)
        file_list = [
            resolver.relative(entry.source)
            for entry in manifest.entries
            if entry.source != pathlib.Path(".")
        ]
        directory_list = [
            entry.destination
            for entry in manifest.entries
            if entry.source == pathlib.Path(".")
        ]

        # check if the same file exists on the remote file
        # only check sha256 when the job is recovered
        if recover:
            # generate local sha256 file
            sha256_list = []
            for jj in file_list:
                sha256 = get_sha256(os.path.join(self.local_root, jj))
                jj_rel = pathlib.PurePath(jj).as_posix()
                sha256_list.append(f"{sha256}  {jj_rel}")
            # write to remote
            sha256_file = pathlib.PurePath(
                os.path.join(self.remote_root, ".tmp.sha256." + str(uuid.uuid4()))
            ).as_posix()
            self.write_file(sha256_file, "\n".join(sha256_list))
            # check sha256
            # `:` means pass: https://stackoverflow.com/a/2421592/9567349
            _, stdout, _ = self.block_checkcall(
                f"sha256sum -c {shlex.quote(sha256_file)} --quiet >.sha256sum_stdout 2>/dev/null || :"
            )
            self.sftp.remove(sha256_file)
            # regenerate file list
            file_list = []

            for ii in self.read_file(".sha256sum_stdout").split("\n"):
                if ii:
                    file_list.append(ii.split(":")[0])
        self._put_files(
            file_list,
            dereference=dereference,
            directories=directory_list,
            tar_compress=bool(self.remote_profile.get("tar_compress", True)),
        )

    def list_remote_dir(
        self,
        sftp: paramiko.SFTPClient,
        remote_dir: str,
        ref_remote_root: str,
        result_list: list[str],
    ) -> None:
        for entry in sftp.listdir_attr(remote_dir):
            remote_name = pathlib.PurePath(
                os.path.join(remote_dir, entry.filename)
            ).as_posix()
            st_mode = entry.st_mode
            if st_mode is None:
                continue
            if S_ISDIR(st_mode):
                self.list_remote_dir(sftp, remote_name, ref_remote_root, result_list)
            elif S_ISREG(st_mode):
                rel_remote_name = os.path.relpath(remote_name, start=ref_remote_root)
                result_list.append(rel_remote_name)

    def download(
        self,
        submission: Submission,
        check_exists: bool = False,
        mark_failure: bool = True,
        back_error: bool = False,
    ) -> None:
        """Download selected remote files using one SFTP-backed manifest.

        Remote wildcard expansion is performed against a single recursive
        SFTP index; the controller's local ``glob`` implementation must never
        be applied to paths that only exist on the remote host.
        """
        assert self.remote_root is not None
        self.ssh_session.ensure_alive()
        remote_files: list[str] = []
        self.list_remote_dir(
            self.sftp, self.remote_root, self.remote_root, remote_files
        )
        builder = RemoteManifestBuilder(
            remote_files,
            exists=self.check_file_exists,
            assume_literals=not check_exists,
        )
        for task in submission.belonging_tasks:
            builder.add_paths(
                source_prefix=task.task_work_path,
                destination_prefix=task.task_work_path,
                patterns=task.backward_files,
                required=True,
            )
            if back_error:
                builder.add_paths(
                    source_prefix=task.task_work_path,
                    destination_prefix=task.task_work_path,
                    patterns=["error*"],
                    required=False,
                )
        builder.add_paths(
            source_prefix=".",
            destination_prefix=".",
            patterns=submission.backward_common_files,
            required=True,
        )
        if back_error:
            builder.add_paths(
                source_prefix=".",
                destination_prefix=".",
                patterns=["error*"],
                required=False,
            )
        manifest = builder.build()
        if manifest.missing and not check_exists:
            missing = manifest.missing[0]
            raise FileNotFoundError(
                "cannot find download file "
                + os.path.join(
                    self.remote_root, missing.destination_prefix, missing.pattern
                )
            )
        if check_exists and mark_failure:
            writer = AtomicTextWriter(self.local_root)
            for missing in manifest.missing:
                writer.write(missing.failure_marker(), "")
        file_list = [entry.destination for entry in manifest.entries]
        if file_list:
            self._get_files(
                file_list,
                tar_compress=bool(self.remote_profile.get("tar_compress", True)),
            )

    def block_call(self, cmd: str) -> tuple[int, Any, Any, Any]:  # noqa: ANN401
        assert self.remote_root is not None
        self.ssh_session.ensure_alive()
        stdin, stdout, stderr = self.ssh_session.exec_command(
            (f"cd {shlex.quote(self.remote_root)} ;") + cmd
        )
        exit_status = stdout.channel.recv_exit_status()
        return exit_status, stdin, stdout, stderr

    def clean(self) -> None:
        self.ssh_session.ensure_alive()
        self._rmtree(self.remote_root)

    def write_file(self, fname: str, write_str: str) -> None:
        assert self.remote_root is not None
        self.ssh_session.ensure_alive()
        fname = (
            PathResolver(self.remote_root)
            .resolve(fname, allow_absolute=True)
            .as_posix()
        )
        # to prevent old file from being overwritten but cancelled, create a temporary file first
        # when it is fully written, rename it to the original file name
        temp_fname = fname + "_tmp"
        try:
            with self.sftp.open(temp_fname, "w") as fp:
                fp.write(write_str)
            # Rename the temporary file
            self.block_checkcall(f"mv {shlex.quote(temp_fname)} {shlex.quote(fname)}")
        # sftp.rename may throw OSError
        except OSError as e:
            dlog.exception(f"Error writing to file {fname}")
            raise e

    def read_file(self, fname: str) -> str:
        assert self.remote_root is not None
        self.ssh_session.ensure_alive()
        with self.sftp.open(
            PathResolver(self.remote_root)
            .resolve(fname, allow_absolute=True)
            .as_posix(),
            "r",
        ) as fp:
            ret = fp.read().decode("utf-8")
        return ret

    def check_file_exists(self, fname: str) -> bool:
        assert self.remote_root is not None
        self.ssh_session.ensure_alive()
        try:
            self.sftp.stat(
                PathResolver(self.remote_root)
                .resolve(fname, allow_absolute=True)
                .as_posix()
            )
            ret = True
        except OSError:
            ret = False
        return ret

    def call(self, cmd: str) -> dict[str, Any]:  # noqa: ANN401
        stdin, stdout, stderr = self.ssh_session.exec_command(cmd)
        # stdin, stdout, stderr = self.ssh.exec_command('echo $$; exec ' + cmd)
        # pid = stdout.readline().strip()
        # print(pid)
        return {"stdin": stdin, "stdout": stdout, "stderr": stderr}

    def check_finish(self, proc: dict[str, Any]) -> bool:  # noqa: ANN401
        return proc["stdout"].channel.exit_status_ready()

    def get_return(self, cmd_pipes: dict[str, Any]) -> tuple[int | None, Any, Any]:  # noqa: ANN401
        if not self.check_finish(cmd_pipes):
            return None, None, None
        else:
            retcode = cmd_pipes["stdout"].channel.recv_exit_status()
            return retcode, cmd_pipes["stdout"], cmd_pipes["stderr"]

    def _rmtree(self, remotepath: str, verbose: bool = False) -> None:
        """Remove the remote path."""
        # The original implementation method removes files one by one using sftp.
        # If the latency of the remote server is high, it is very slow.
        # Thus, it's better to use system's `rm` to remove a directory, which may
        # save a lot of time.
        if verbose:
            dlog.info(f"removing {remotepath}")
        # In some supercomputers, it's very slow to remove large numbers of files
        # (e.g. directory containing trajectory) due to bad I/O performance.
        # So an asynchronously option is provided.
        self.block_checkcall(
            f"rm -rf {shlex.quote(remotepath)}",
            asynchronously=self.clean_asynchronously,
        )

    def _put_files(
        self,
        files: list[str],
        dereference: bool = True,
        directories: list[str] | None = None,
        tar_compress: bool = True,
    ) -> None:
        """Upload files to server.

        Parameters
        ----------
        files : list
            uploaded files
        dereference : bool, default: True
            If dereference is False, add symbolic and hard links to the archive.
            If it is True, add the content of the target files to the archive.
            This has no effect on systems that do not support symbolic links.
        directories : list, default: None
            uploaded directories non-recursively. Use `files` for uploading
            recursively
        tar_compress : bool, default: True
            If tar_compress is True, compress the archive using gzip
            It it is False, then it is uncompressed
        """
        assert self.submission.submission_hash is not None
        assert self.remote_root is not None
        of_suffix = ".tgz"
        if not tar_compress:
            of_suffix = ".tar"

        of = self.submission.submission_hash + of_suffix
        # local tar
        if os.path.isfile(os.path.join(self.local_root, of)):
            os.remove(os.path.join(self.local_root, of))
        with (
            tarfile.open(
                os.path.join(self.local_root, of),
                mode="w:gz",
                dereference=dereference,
                compresslevel=6,
            )
            if tar_compress
            else tarfile.open(
                os.path.join(self.local_root, of),
                mode="w",
                dereference=dereference,
            )
        ) as tar:
            # avoid compressing duplicated files or directories
            for ii in set(files):
                ii_full = os.path.join(self.local_root, ii)
                tar.add(ii_full, arcname=ii)
            if directories is not None:
                for ii in set(directories):
                    ii_full = os.path.join(self.local_root, ii)
                    tar.add(ii_full, arcname=ii, recursive=False)
        self.ssh_session.ensure_alive()
        try:
            self.sftp.mkdir(self.remote_root)
        except OSError:
            pass
        # trans
        from_f = pathlib.PurePath(os.path.join(self.local_root, of)).as_posix()
        to_f = pathlib.PurePath(os.path.join(self.remote_root, of)).as_posix()
        try:
            self.ssh_session.put(from_f, to_f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"from {from_f} to {self.ssh_session.username} @ {self.ssh_session.hostname} : {to_f} Error!"
            )
        # remote extract
        self.block_checkcall(f"tar xf {of}")
        # clean up
        os.remove(from_f)
        self.sftp.remove(to_f)

    def _get_files(self, files: list[str], tar_compress: bool = True) -> None:
        assert self.submission.submission_hash is not None
        assert self.remote_root is not None
        # avoid compressing duplicated files
        files = list(set(files))

        of_suffix = ".tar.gz"
        tarfile_mode = "r:gz"
        tar_command = "czfh"
        if not tar_compress:
            of_suffix = ".tar"
            tarfile_mode = "r"
            tar_command = "cfh"

        of = self.submission.submission_hash + of_suffix
        # remote tar
        # If the number of files are large, we may get "Argument list too long" error.
        # Thus, "-T" accepts a file containing the list of files
        per_nfile = 100
        ntar = len(files) // per_nfile + 1
        if ntar <= 1:
            file_list = " ".join([shlex.quote(file) for file in files])
            tar_cmd = f"tar {tar_command} {shlex.quote(of)} {file_list}"
        else:
            file_list_file = pathlib.PurePath(
                os.path.join(self.remote_root, f".tmp_tar_{uuid.uuid4()}")
            ).as_posix()
            self.write_file(file_list_file, "\n".join(files))
            tar_cmd = (
                f"tar {tar_command} {shlex.quote(of)} -T {shlex.quote(file_list_file)}"
            )

        # Execute the tar command remotely
        try:
            self.block_checkcall(tar_cmd)
        except RuntimeError as e:
            if "No such file or directory" in str(e):
                raise FileNotFoundError(
                    "Backward files do not exist in the remote directory."
                ) from e
            raise e

        # Transfer the archive from remote to local
        from_f = pathlib.PurePath(os.path.join(self.remote_root, of)).as_posix()
        to_f = pathlib.PurePath(os.path.join(self.local_root, of)).as_posix()
        if os.path.isfile(to_f):
            os.remove(to_f)
        self._get_archive(from_f, to_f)
        # extract
        with tarfile.open(to_f, mode=tarfile_mode) as tar:
            safe_extract_tar(tar, self.local_root)
        # cleanup
        os.remove(to_f)
        self.sftp.remove(from_f)

    def _get_archive(self, remote_archive: str, local_archive: str) -> None:
        """Download one remote archive, optionally through bounded-size parts.

        Splitting is opt-in because it depends on the remote ``split`` utility.
        Each part is removed after it is appended locally, so temporary local
        storage is bounded by the archive plus one configured-size part.

        Parameters
        ----------
        remote_archive : str
            Absolute path of the archive on the remote host.
        local_archive : str
            Absolute path where the reconstructed archive is written locally.
        """
        chunk_size = self.ssh_session.archive_chunk_size
        if chunk_size == 0:
            self.ssh_session.get(remote_archive, local_archive)
            return
        if chunk_size < 0:
            raise ValueError("archive_chunk_size must be greater than or equal to 0")

        remote_directory = posixpath.dirname(remote_archive)
        chunk_basename_prefix = f".dpdispatcher-archive-{uuid.uuid4().hex}-"
        chunk_prefix = posixpath.join(remote_directory, chunk_basename_prefix)
        local_chunk = ""
        assembled = False
        try:
            expected_size = self.sftp.stat(remote_archive).st_size
            split_command = (
                f"split -b {chunk_size} -a 6 "
                f"{shlex.quote(remote_archive)} {shlex.quote(chunk_prefix)}"
            )
            self.block_checkcall(split_command)

            remote_chunks = [
                posixpath.join(remote_directory, filename)
                for filename in sorted(self.sftp.listdir(remote_directory))
                if filename.startswith(chunk_basename_prefix)
            ]
            if not remote_chunks:
                raise RuntimeError(
                    "The remote split command produced no archive parts; "
                    "check that `split` is available on the SSH host."
                )

            with open(local_archive, "wb") as assembled_archive:
                for index, remote_chunk in enumerate(remote_chunks):
                    local_chunk = f"{local_archive}.part-{index:06d}"
                    self.ssh_session.get(remote_chunk, local_chunk)
                    with open(local_chunk, "rb") as chunk_file:
                        shutil.copyfileobj(chunk_file, assembled_archive)
                    os.remove(local_chunk)
                    local_chunk = ""

            actual_size = os.path.getsize(local_archive)
            if actual_size != expected_size:
                raise OSError(
                    "Reconstructed archive size does not match the remote archive: "
                    f"expected {expected_size} bytes, got {actual_size} bytes"
                )
            assembled = True
        finally:
            if local_chunk and os.path.exists(local_chunk):
                try:
                    os.remove(local_chunk)
                except OSError as error:
                    dlog.debug(
                        f"Could not remove temporary local archive part "
                        f"{local_chunk}: {error}"
                    )
            if not assembled and os.path.exists(local_archive):
                try:
                    os.remove(local_archive)
                except OSError as error:
                    dlog.debug(
                        f"Could not remove incomplete local archive "
                        f"{local_archive}: {error}"
                    )
            try:
                discovered_chunks = [
                    posixpath.join(remote_directory, filename)
                    for filename in sorted(self.sftp.listdir(remote_directory))
                    if filename.startswith(chunk_basename_prefix)
                ]
            except Exception as error:
                dlog.debug(
                    f"Could not discover temporary remote archive parts "
                    f"with prefix {chunk_basename_prefix}: {error}"
                )
                discovered_chunks = []
            for remote_chunk in discovered_chunks:
                try:
                    self.sftp.remove(remote_chunk)
                except Exception as error:
                    dlog.debug(
                        f"Could not remove temporary remote archive part "
                        f"{remote_chunk}: {error}"
                    )

    @classmethod
    def machine_subfields(cls) -> list[Argument]:
        """Generate the machine subfields.

        Returns
        -------
        list[Argument]
            machine subfields
        """
        doc_create_remote_root = (
            "Whether DPDispatcher should recursively create the configured SSH remote_root "
            "when parent directories do not already exist. Keep this disabled by default "
            "to avoid silently creating directories for a mistyped path."
        )
        doc_remote_profile = "SSH connection settings for the remote machine, including authentication, timeouts, and optional proxy/jump-host behavior."
        remote_profile_format = SSHSession.arginfo()
        remote_profile_format.name = "remote_profile"
        remote_profile_format.doc = doc_remote_profile
        return [
            Argument(
                "create_remote_root",
                bool,
                optional=True,
                default=False,
                doc=doc_create_remote_root,
            ),
            remote_profile_format,
        ]
