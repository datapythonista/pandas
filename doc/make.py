#!/usr/bin/env python
"""
Python script for building documentation.

To build the docs you must have all optional dependencies for pandas
installed. See the installation instructions for a list of these.

Usage
-----
    $ python make.py clean
    $ python make.py html
    $ python make.py latex
"""
import sys
import os
import shutil
import subprocess
import argparse
import tempfile
from contextlib import contextmanager
import jinja2


DOC_PATH = os.path.dirname(os.path.abspath(__file__))
SOURCE_PATH = os.path.join(DOC_PATH, 'source')
BUILD_PATH = os.path.join(DOC_PATH, 'build')
BUILD_DIRS = ['doctrees', 'html', 'latex', 'plots', '_static', '_templates']


def _generate_index(include_api, single_doc=None):
    """Create index.rst file with the specified sections.

    Parameters
    ----------
    include_api : bool
        Whether API documentation will be built.
    single_doc : str or None
        If provided, this single documentation page will be generated.
    """
    if single_doc is not None:
        single_doc = os.path.splitext(os.path.basename(single_doc))[0]
        include_api = False

    with open(os.path.join(SOURCE_PATH, 'index.rst.template')) as f:
        t = jinja2.Template(f.read())

    with open(os.path.join(SOURCE_PATH, 'index.rst'), 'w') as f:
        f.write(t.render(include_api=include_api,
                         single_doc=single_doc))


@contextmanager
def _maybe_exclude_notebooks():
    """Skip building the notebooks if pandoc is not installed.

    This assumes that nbsphinx is installed.

    Skip notebook conversion if:
    1. nbconvert isn't installed, or
    2. nbconvert is installed, but pandoc isn't
    """
    base = os.path.dirname(__file__)
    notebooks = [os.path.join(base, 'source', nb)
                 for nb in ['style.ipynb']]
    contents = {}

    def _remove_notebooks():
        for nb in notebooks:
            with open(nb, 'rt') as f:
                contents[nb] = f.read()
            os.remove(nb)

    try:
        import nbconvert
    except ImportError:
        sys.stderr.write('Warning: nbconvert not installed. '
                         'Skipping notebooks.\n')
        _remove_notebooks()
    else:
        try:
            nbconvert.utils.pandoc.get_pandoc_version()
        except nbconvert.utils.pandoc.PandocMissing:
            sys.stderr.write('Warning: Pandoc is not installed. '
                             'Skipping notebooks.\n')
            _remove_notebooks()

    yield

    for nb, content in contents.items():
        with open(nb, 'wt') as f:
            f.write(content)


class DocBuilder:
    """Class to wrap the different commands of this script.

    All public methods of this class can be called as parameters of the
    script.
    """
    def __init__(self, num_jobs=1):
        self.num_jobs = num_jobs

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
        >>> DocBuilder()._run_os('python', '--version')
        """
        subprocess.check_call(args, stderr=subprocess.STDOUT)

    def _sphinx_build(self, kind, source_path=None, build_path=None):
        """Call sphinx to build documentation.

        Attribute `num_jobs` from the class is used.

        Parameters
        ----------
        kind : {'html', 'latex'}
        source_path: str or None
            Directory with the sources to build
        build_path: str or None
            Target directory where built files will be generated

        Examples
        --------
        >>> DocBuilder(num_jobs=4)._sphinx_build('html')
        """
        if kind not in ('html', 'latex'):
            raise ValueError('kind must be html or latex, not {}'.format(kind))

        if source_path is None:
            source_path = SOURCE_PATH
        if build_path is None:
            build_path = os.path.join(BUILD_PATH, kind)

        self._run_os('sphinx-build',
                     '-j{}'.format(self.num_jobs),
                     '-b{}'.format(kind),
                     '-d{}'.format(os.path.join(BUILD_PATH,
                                                'doctrees')),
                     source_path,
                     build_path)

    def html(self):
        """Build HTML documentation."""
        self._create_build_structure()
        with _maybe_exclude_notebooks():
            self._sphinx_build('html')
            zip_fname = os.path.join(BUILD_PATH, 'html', 'pandas.zip')
            if os.path.exists(zip_fname):
                os.remove(zip_fname)

    def latex(self, force=False):
        """Build PDF documentation."""
        self._create_build_structure()
        if sys.platform == 'win32':
            sys.stderr.write('latex build has not been tested on windows\n')
        else:
            self._sphinx_build('latex')
            os.chdir(os.path.join(BUILD_PATH, 'latex'))
            if force:
                for i in range(3):
                    self._run_os('pdflatex',
                                 '-interaction=nonstopmode',
                                 'pandas.tex')
                raise SystemExit('You should check the file '
                                 '"build/latex/pandas.pdf" for problems.')
            else:
                self._run_os('make')

    def latex_forced(self):
        """Build PDF documentation with retries to find missing references."""
        self.latex(force=True)

    @staticmethod
    def clean():
        """Clean documentation generated files."""
        shutil.rmtree(BUILD_PATH, ignore_errors=True)
        shutil.rmtree(os.path.join(SOURCE_PATH, 'generated'),
                      ignore_errors=True)

    def zip_html(self):
        """Compress HTML documentation into a zip file."""
        zip_fname = os.path.join(BUILD_PATH, 'html', 'pandas.zip')
        if os.path.exists(zip_fname):
            os.remove(zip_fname)
        dirname = os.path.join(BUILD_PATH, 'html')
        fnames = os.listdir(dirname)
        os.chdir(dirname)
        self._run_os('zip',
                     zip_fname,
                     '-r',
                     '-q',
                     *fnames)

    def html_single(self, method='pandas.DataFrame.reset_index'):
        # TODO: call apidoc?
        temp_dir = tempfile.mkdtemp()
        os.mkdir(os.path.join(temp_dir, 'source'))
        os.mkdir(os.path.join(temp_dir, 'build'))
        symlinks = ('sphinxext',
                    '_templates',
                    os.path.join('source', '_static'),
                    os.path.join('source', 'themes'))
        for dirname in symlinks:
            os.symlink(os.path.join(DOC_PATH, dirname),
                       os.path.join(temp_dir, dirname),
                       target_is_directory=True)
        os.symlink(os.path.join(DOC_PATH, 'source', 'conf.py'),
                   os.path.join(temp_dir, 'source', 'conf.py'),
                   target_is_directory=False)
        os.symlink(os.path.join(DOC_PATH, 'source', 'generated',
                                '{}.rst'.format(method)),
                   os.path.join(temp_dir, 'source', '{}.rst'.format(method)),
                   target_is_directory=False)

        idx_content = '.. toctree::\n\t:maxdepth: 2\n\t\n\t{}'.format(method)
        with open(os.path.join(temp_dir, 'source', 'index.rst'), 'w') as f:
            f.write(idx_content)

        self._sphinx_build('html',
                           os.path.join(temp_dir, 'source'),
                           os.path.join(temp_dir, 'build'))

        os.makedirs(os.path.join(BUILD_PATH, 'html', 'generated'))
        shutil.copy(
            os.path.join(temp_dir, 'build', '{}.html'.format(method)),
            os.path.join(BUILD_PATH, 'html', 'generated',
                         '{}.html'.format(method)))
        shutil.rmtree(temp_dir)


def main():
    cmds = [method for method in dir(DocBuilder) if not method.startswith('_')]

    argparser = argparse.ArgumentParser(
        description='pandas documentation builder',
        epilog='Commands: {}'.format(','.join(cmds)))
    argparser.add_argument('command',
                           nargs='?',
                           default='html',
                           help='command to run: {}'.format(', '.join(cmds)))
    argparser.add_argument('--num-jobs',
                           type=int,
                           default=1,
                           help='number of jobs used by sphinx-build')
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
    argparser.add_argument('--python-path',
                           type=str,
                           default=os.path.join(DOC_PATH, '..'),
                           help='path')
    args = argparser.parse_args()

    if args.command not in cmds:
        raise ValueError('Unknown command {}. Available options: {}'.format(
            args.command, ', '.join(cmds)))

    os.environ['PYTHONPATH'] = args.python_path
    _generate_index(not args.no_api, args.single)
    getattr(DocBuilder(args.num_jobs), args.command)()


if __name__ == '__main__':
    sys.exit(main())
