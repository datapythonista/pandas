#!/usr/bin/env python
"""
Python script for building documentation.

To build the docs you must have all optional dependencies for pandas
installed. See the installation instructions for a list of these.

<del>Note: currently latex builds do not work because of table formats that
are not supported in the latex generation.</del>

2014-01-30: Latex has some issues but 'latex_forced' works ok for 0.13.0-400
or so

Usage
-----
    $ python make.py clean
    $ python make.py html
"""
import sys
import os
import shutil
import subprocess
import argparse
import base64
import smtplib
from email.MIMEText import MIMEText
import jinja2


DOC_PATH = os.path.dirname(os.path.abspath(__file__))
SOURCE_PATH = os.path.join(DOC_PATH, 'source')
BUILD_PATH = os.path.join(DOC_PATH, 'build')
BUILD_DIRS = ['doctrees', 'html', 'latex', 'plots', '_static', '_templates']
SERVER_HOST = 'pandas.pydata.org'
SERVER_BASE_PATH = '/usr/share/nginx/pandas/pandas-docs'


def _generate_index(include_api, include_notebooks, single_doc=None):
    """Create index.rst file with the specified sections.

    Parameters
    ----------
    include_api : bool
        Whether API documentation will be built.
    include_notebooks : bool
        Whether .ipynb will be included in the documentation. Requires
        nbconvert and pandoc installed.
    single_doc : str or None
        If provided, this single documentation page will be generated.
    """
    def _can_handle_notebooks():
        try:
            import nbconvert
        except ImportError:
            return False
        else:
            try:
                nbconvert.utils.pandoc.get_pandoc_version()
            except nbconvert.utils.pandoc.PandocMissing:
                return False
        return True

    if single_doc is not None:
        single_doc = os.path.basename(single_doc).splitext()[0]
        include_api = False
        include_notebooks = False
    if include_notebooks and not _can_handle_notebooks():
        raise ImportError('option --include-notebooks used, '
                          'but nbconvert or pandoc are not installed')

    with open(os.path.join(SOURCE_PATH, 'index.rst.template')) as f:
        t = jinja2.Template(f.read())

    with open(os.path.join(SOURCE_PATH, 'index.rst'), 'w') as f:
        f.write(t.render(include_api=include_api,
                         include_notebooks=include_notebooks,
                         single_doc=single_doc))


class DocTools:
    """Class to wrap the different commands of this script.

    All public methods of this class can be called as parameters of the
    script.
    """
    num_jobs = 1
    user = None
    version = None

    @staticmethod
    def _create_build_structure():
        """Create directories required to build documentation."""
        for dirname in BUILD_DIRS:
            try:
                os.makedirs(os.path.join(BUILD_PATH, dirname))
            except OSError:
                pass

    @staticmethod
    def _run_os(*args):
        """Execute a command as a OS terminal.

        Parameters
        ----------
        *args : list of str
            Command and parameters to be executed

        Examples
        --------
        >>> DocTools._run_os('python', '--version')
        """
        subprocess.check_call(args, stderr=subprocess.STDOUT)

    @classmethod
    def _sphinx_build(cls, kind):
        """Call sphinx to build documentation.

        Attribute `num_jobs` from the class is used.

        Parameters
        ----------
        kind : {'html', 'latex'}

        Examples
        --------
        >>> DocTools.num_jobs = 4
        >>> DocTools._sphinx_build('html')
        """
        if kind not in ('html', 'latex'):
            raise ValueError('kind must be html or latex, not {}'.format(kind))

        cls._run_os('sphinx-build',
                    '-j{}'.format(cls.num_jobs),
                    '-b{}'.format(kind),
                    '-d{}'.format(os.path.join(BUILD_PATH,
                                               'doctrees')),
                    SOURCE_PATH,
                    os.path.join(BUILD_PATH, kind))

    @classmethod
    def _upload_doc(cls, kind, version):
        """Upload pandas documentation to the PyData server.

        Parameters
        ----------
        kind : {'html', 'pdf'}
            Type of documentation to upload
        version : {'dev', 'stable'} or str
            Environment or version where to upload the documentation
        """
        if kind == 'html':
            cmd = ['rsync', '-avz', '-essh', os.path.join(BUILD_PATH, 'html')]
        elif kind == 'latex':
            cmd = ['scp', os.path.join(BUILD_PATH, 'latex', 'pandas.pdf')]
        else:
            raise ValueError(('Unknown document kind "{}". '
                              'Must be html or latex'.format(kind)))
        if version not in ('dev', 'stable'):
            version = 'version/{}'.format(version)

        remote_path = '{path}/{version}/'.format(path=SERVER_BASE_PATH,
                                                 version=version)
        cmd.append('{user}{at}{host}:{path}'.format(user=cls.user or '',
                                                    at='@' if cls.user else '',
                                                    host=SERVER_HOST,
                                                    path=remote_path))
        cls._run_os(*cmd)

    @staticmethod
    def _sendmail(step='', err_msg=None):
        """Send an email with a succesful build message, or an error."""
        config_dir = os.path.join(os.path.expanduser('~'),
                                  'code',
                                  'scripts',
                                  'config')

        with open(os.path.join(config_dir, 'credentials'), 'r') as f:
            server_str, port, un, domain = f.read().split(',')
        port = int(port)
        login = un + '@' + domain + '.com'

        with open(os.path.join(config_dir, 'cron_email_pwd'), 'r') as f:
            pwd = base64.b64decode(f.read())

        with open(os.path.join(config_dir, 'addresses'), 'r') as f:
            from_name, to_name = f.read().split(',')

        subject = 'DOC: {} '.format(step)
        if err_msg is None or '[ERROR]' not in err_msg:
            msgstr = 'Daily docs {} completed successfully'.format(step)
            subject += 'successful'
        else:
            msgstr = err_msg
            subject += 'failed'

        msg = MIMEText(msgstr)
        msg['Subject'] = subject
        msg['From'] = from_name
        msg['To'] = to_name
        server = smtplib.SMTP(server_str, port)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(login, pwd)
        try:
            server.sendmail(from_name, to_name, msg.as_string())
        finally:
            server.close()

    @classmethod
    def html(cls):
        """Build HTML documentation."""
        cls._create_build_structure()
        cls._sphinx_build('html')

    @classmethod
    def zip_html(cls):
        """Compress HTML documentation into a zip file."""
        zip_fname = os.path.join(BUILD_PATH, 'html', 'pandas.zip')
        if os.path.exists(zip_fname):
            os.remove(zip_fname)
        dirname = os.path.join(BUILD_PATH, 'html')
        fnames = os.listdir(dirname)
        os.chdir(dirname)
        cls._run_os('zip',
                    zip_fname,
                    '-r',
                    '-q',
                    *fnames)

    @classmethod
    def upload_dev(cls):
        """Upload HTML development documentation to the server."""
        cls._upload_doc(kind='html', version='dev')

    @classmethod
    def upload_stable(cls):
        """Upload HTML stable documentation to the server."""
        cls._upload_doc(kind='html', version='stable')

    @classmethod
    def upload_dev_pdf(cls):
        """Upload PDF development documentation to the server."""
        cls._upload_doc(kind='latex', version='dev')

    @classmethod
    def upload_stable_pdf(cls):
        """Upload PDF stable documentation to the server."""
        cls._upload_doc(kind='latex', version='stable')

    @classmethod
    def latex(cls, force=False):
        """Build PDF documentation."""
        cls._create_build_structure()
        if sys.platform == 'win32':
            sys.stderr.write('latex build has not been tested on windows\n')
        else:
            cls._sphinx_build('latex')
            os.chdir(os.path.join(BUILD_PATH, 'latex'))
            if force:
                for i in range(3):
                    cls._run_os('pdflatex',
                                '-interaction=nonstopmode',
                                'pandas.tex')
                raise SystemExit('You should check the file '
                                 '"build/latex/pandas.pdf" for problems.')
            else:
                cls._run_os('make')

    @classmethod
    def latex_forced(cls):
        """Build PDF documentation with retries to find missing references."""
        cls.latex(force=True)

    @staticmethod
    def clean():
        """Clean documentation generated files."""
        shutil.rmtree(BUILD_PATH, ignore_errors=True)
        shutil.rmtree(os.path.join(SOURCE_PATH, 'generated'),
                      ignore_errors=True)

    @classmethod
    def auto_dev(cls, debug=False):
        """Build and upload HTML and PDF documentation."""
        msg = ''
        try:
            step = 'clean'
            cls.clean()
            step = 'html'
            cls.html()
            step = 'upload dev'
            cls.upload_dev()
            if not debug:
                cls._sendmail(step)
            step = 'latex'
            cls.latex()
            step = 'upload pdf'
            cls.upload_dev_pdf()
            if not debug:
                cls._sendmail(step)
        except (Exception, SystemExit) as inst:
            msg = str(inst) + '\n'
            cls._sendmail(step, '[ERROR] ' + msg)

    @classmethod
    def auto_debug(cls):
        """Build and upload HTML and PDF documentation with success emails."""
        cls.auto_dev(debug=True)

    @classmethod
    def build_pandas(cls):
        """Compile pandas cython extension."""
        os.chdir('..')
        cls._run_os('python',
                    'setup.py',
                    'clean')
        cls._run_os('python',
                    'setup.py',
                    'build_ext',
                    '--inplace')
        os.chdir('doc')

    @classmethod
    def all(cls):
        """Alias to build HTML by default."""
        cls.html()

    @classmethod
    def build_previous(cls):
        """Build a previous version of the documentation.

        Version is specified in the `DocTools.version` attribute.
        """
        if cls.version is None:
            raise ValueError('Version must be specified '
                             'for command build_previous')
        cls._run_os('git', 'checkout', 'c{}'.format(cls.version))
        cls.build_pandas()
        cls.clean()
        cls.html()
        cls.latex()
        cls._run_os('git', 'checkout', 'master')

    @classmethod
    def upload_previous(cls):
        """Upload a previous version of the documentation.

        Version is specified in the `DocTools.version` attribute.
        """
        if cls.version is None:
            raise ValueError('Version must be specified '
                             'for command upload_previous')
        cls._upload_doc('html', cls.version)
        cls._upload_doc('latex', cls.version)


def main():
    cmds = [method for method in dir(DocTools) if not method.startswith('_')]
    version_cmds = [cmd for cmd in cmds if cmd.endswith('_previous')]

    argparser = argparse.ArgumentParser(
        description='pandas documentation builder',
        epilog='Commands: {}'.format(','.join(cmds)))
    argparser.add_argument('command',
                           nargs='?',
                           default='all',
                           help='command to run: {}'.format(', '.join(cmds)))
    argparser.add_argument('--no-api',
                           default=False,
                           help='ommit api and autosummary',
                           action='store_true')
    argparser.add_argument('--single',
                           metavar='FILENAME',
                           type=str,
                           default=None,
                           help=('filename of section to compile, '
                                 'e.g. "indexing"'))
    argparser.add_argument('--num-jobs',
                           type=int,
                           default=1,
                           help='number of jobs used by sphinx-build')
    argparser.add_argument('--user',
                           type=str,
                           default=None,
                           help='username to connect to the pydata server')
    argparser.add_argument('version',
                           nargs='?',
                           help='git version. Only used with: {}'.format(
                               ', '.join(version_cmds)))
    argparser.add_argument('--include-notebooks',
                           default=False,
                           help='include ipython notebooks',
                           action='store_true')
    argparser.add_argument('--python-path',
                           type=str,
                           default=os.path.join(DOC_PATH, '..'),
                           help='path')
    args = argparser.parse_args()

    if args.command not in cmds:
        raise ValueError('Unknown command {}. Available options: {}'.format(
            args.command, ', '.join(cmds)))

    os.environ['PYTHONPATH'] = args.python_path

    _generate_index(not args.no_api, args.include_notebooks, args.single)

    DocTools.user = args.user
    DocTools.num_jobs = args.num_jobs
    DocTools.version = args.version
    getattr(DocTools, args.command)()


if __name__ == '__main__':
    sys.exit(main())
