# -*- coding: utf-8 -*-
# This file is execfile()d with the current directory set to its containing dir.
#
# Note that not all possible configuration values are present in this autogenerated file.
#
# All configuration values have a default; values that are commented out serve to show the default.
from __future__ import print_function, absolute_import, unicode_literals, division

import sys
import os
import shutil
#import matplotlib as mpl
#mpl.use("Agg")

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

ABIPY_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
#print(ABIPY_ROOT)

sys.path.insert(0, ABIPY_ROOT)


import imp
mod_name = os.path.join(ABIPY_ROOT, "abipy", "core", "release.py")
relmod = imp.load_source(mod_name, mod_name)

on_rtd = os.environ.get('READTHEDOCS') == 'True' and os.environ.get("READTHEDOCS_PROJECT")
if on_rtd:
    print("Preparing execution on READTHEDOCS server...")
    os.makedirs(os.path.expanduser("~/.abinit/abipy"))
    shutil.copy(os.path.join(ABIPY_ROOT, "data", "managers", "travis_scheduler.yml"),
                os.path.expanduser("~/.abinit/abipy/scheduler.yml"))
    shutil.copy(os.path.join(ABIPY_ROOT, "data", "managers", "travis_manager.yml"),
                os.path.expanduser("~/.abinit/abipy/manager.yml"))

# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.doctest',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.mathjax',
    'sphinx.ext.ifconfig',
    'sphinx.ext.viewcode',
    'sphinx.ext.graphviz',
    'sphinx.ext.napoleon',   # For Google Python Style Guide
    'sphinx.ext.inheritance_diagram',
    'sphinxcontrib.programoutput',
    'sphinx_gallery.gen_gallery',
    "sphinxarg.ext",         # CLI doc
    'sphinxcontrib.bibtex',
    "releases",
    #'nbsphinx',
    #'sphinx.ext.coverage',

]

# Add any Sphinx extension module names here, as strings. They can
# be extensions coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
import matplotlib
extensions += [
    'matplotlib.sphinxext.only_directives',
    'matplotlib.sphinxext.plot_directive',
    'IPython.sphinxext.ipython_directive',
    'IPython.sphinxext.ipython_console_highlighting',
]

# Add local extensions (not available on PyPi)
sys.path.insert(0, os.path.join(ABIPY_ROOT, "docs", "my_extensions"))
extensions += [
    'youtube',
]

from sphinx_gallery.sorting import FileNameSortKey, NumberOfCodeLinesSortKey
sphinx_gallery_conf = {
    # path to your examples scripts
    'examples_dirs': ["../abipy/examples/plot", "../abipy/examples/flows",],
    # path where to save gallery generated examples
    'gallery_dirs': ["gallery", "flow_gallery",],
    'filename_pattern': "(/plot_*|/run_*)",
    'default_thumb_file': '_static/abipy_logo.png',
    'within_subsection_order': NumberOfCodeLinesSortKey,
    'backreferences_dir': False,
    #'find_mayavi_figures': True,
    'reference_url': {
        'abipy': None,  # The module you locally document uses None
        'numpy': 'https://docs.scipy.org/doc/numpy/',
        'matplotlib': 'https://matplotlib.org',
        'pandas': "http://pandas-docs.github.io/pandas-docs-travis/",
        "pymatgen": "http://pymatgen.org/",
    },
    # TODO
    #https://sphinx-gallery.github.io/advanced_configuration.html#generate-binder-links-for-gallery-notebooks-experimental
    #'binder': {
    #    'org': 'abinit',
    #    #'repo': 'abipy',
    #    #'repo': 'https://github.com/abinit/abipy',
    #    "repo": "http://abinit.github.io/abipy/",
    #    'url': 'https://mybinder.org', # URL serving binders (e.g. mybinder.org)
    #    'branch': 'develop',  # Can also be a tag or commit hash
    #    'dependencies': '../binder/environment.yml' # list_of_paths_to_dependency_files>'
    # },
}

# Generate the API documentation when building
autosummary_generate = True
numpydoc_show_class_members = False

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
source_encoding = 'utf-8'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = 'abipy'
copyright = '2018, ' + relmod.author

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = relmod.__version__
# The full version, including alpha/beta/rc tags.
release = relmod.__version__

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#language = None

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
#today_fmt = '%B %d, %Y'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build', '**.ipynb_checkpoints', "links.rst"]

# The reST default role (used for this markup: `text`) to use for all documents.
#default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
#add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
#add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
#show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# A list of ignored prefixes for module index sorting.
#modindex_common_prefix = []


# -- Options for HTML output ---------------------------------------------------

# Activate the theme.
import sphinx_bootstrap_theme
html_theme = 'bootstrap'
html_theme_path = sphinx_bootstrap_theme.get_html_theme_path()

# (Optional) Logo. Should be small enough to fit the navbar (ideally 24x24).
# Path should be relative to the ``_static`` files directory.
#html_logo = "my_logo.png"

# Theme options are theme-specific and customize the look and feel of a
# theme further.
html_theme_options = {
    # Navigation bar title. (Default: ``project`` value)
    #'navbar_title': "Demo",

    # Tab name for entire site. (Default: "Site")
    'navbar_site_name': "Site",

    # A list of tuples containing pages or urls to link to.
    # Valid tuples should be in the following forms:
    #    (name, page)                 # a link to a page
    #    (name, "/aa/bb", 1)          # a link to an arbitrary relative url
    #    (name, "http://example.com", True) # arbitrary absolute url
    # Note the "1" or "True" value above as the third argument to indicate
    # an arbitrary url.
    #'navbar_links': [
    #    ("Examples", "examples"),
    #    ("Link", "http://example.com", True),
    #],

    # Render the next and previous page links in navbar. (Default: true)
    'navbar_sidebarrel': True,

    # Render the current pages TOC in the navbar. (Default: true)
    'navbar_pagenav': True,

    # Tab name for the current pages TOC. (Default: "Page")
    'navbar_pagenav_name': "Page",

    # Global TOC depth for "site" navbar tab. (Default: 1)
    # Switching to -1 shows all levels.
    'globaltoc_depth': 1,

    # Include hidden TOCs in Site navbar?
    #
    # Note: If this is "false", you cannot have mixed ``:hidden:`` and
    # non-hidden ``toctree`` directives in the same page, or else the build
    # will break.
    #
    # Values: "true" (default) or "false"
    'globaltoc_includehidden': "true",

    # HTML navbar class (Default: "navbar") to attach to <div> element.
    # For black navbar, do "navbar navbar-inverse"
    #'navbar_class': "navbar navbar-inverse",

    # Fix navigation bar to top of page?
    # Values: "true" (default) or "false"
    'navbar_fixed_top': "true",

    # Location of link to source.
    # Options are "nav" (default), "footer" or anything else to exclude.
    'source_link_position': "nav",

    # Bootswatch (http://bootswatch.com/) theme.
    # Options are nothing (default) or the name of a valid theme
    # such as "cosmo" or "sandstone".
    #'bootswatch_theme': "united",
    #'bootswatch_theme': "flatly",
    #'bootswatch_theme': "litera",
    #'bootswatch_theme': "simplex",
    #'bootswatch_theme': "sandstone",

    # Choose Bootstrap version.
    # Values: "3" (default) or "2" (in quotes)
    'bootstrap_version': "3",
}


def setup(app):
    """
    Sphinx automatically calls your setup function defined in "conf.py" during the build process for you.
    There is no need to, nor should you, call this function directly in your code.
    http://www.sphinx-doc.org/en/stable/extdev/appapi.html
    """
    # Add custom css in _static
    app.add_stylesheet("my_style.css")


# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
#html_title = None

# A shorter title for the navigation bar.  Default is the same as html_title.
#html_short_title = None

# The name of an image file (relative to this directory) to place at the top of the sidebar.
#html_logo = "_static/abipy_logo.png"

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
#html_favicon = None

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
#html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
#html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
#html_additional_pages = {}

# If false, no module index is generated.
#html_domain_indices = True

# If false, no index is generated.
#html_use_index = True

# If true, the index is split into individual pages for each letter.
#html_split_index = False

# If true, links to the reST sources are added to the pages.
#html_show_sourcelink = True

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
#html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
#html_show_copyright = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#html_use_opensearch = ''

# This is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = None

# Output file base name for HTML help builder.
htmlhelp_basename = 'abipydoc'


# -- Options for LaTeX output --------------------------------------------------

latex_elements = {
# The paper size ('letterpaper' or 'a4paper').
#'papersize': 'letterpaper',

# The font size ('10pt', '11pt' or '12pt').
#'pointsize': '10pt',

# Additional stuff for the LaTeX preamble.
#'preamble': '',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', 'abipy.tex', 'AbiPy Documentation', 'M. Giantomassi', 'manual'),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
#latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#latex_use_parts = False

# If true, show page references after internal links.
#latex_show_pagerefs = False

# If true, show URL addresses after external links.
#latex_show_urls = False

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_domain_indices = True


# -- Options for manual page output --------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('index', 'abipy', 'abipy Documentation',
     ", ".join(list(a[0] for a in relmod.authors.values())), 1)
]

# If true, show URL addresses after external links.
#man_show_urls = False


# -- Options for Texinfo output ------------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
  ('index', 'abipy', 'abipy Documentation',
   'M. Giantomassi', 'abipy', 'One line description of project.',
   'Miscellaneous'),
]

# Documents to append as an appendix to all manuals.
#texinfo_appendices = []

# If false, no module index is generated.
#texinfo_domain_indices = True

# How to display URL addresses: 'footnote', 'no', or 'inline'.
#texinfo_show_urls = 'footnote'

# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    'python': ('https://docs.python.org/{.major}'.format(sys.version_info), None),
    'numpy': ('https://docs.scipy.org/doc/numpy/', None),
    "scipy": ("https://docs.scipy.org/doc/scipy/reference/", None),
    'pandas': ("http://pandas-docs.github.io/pandas-docs-travis/", None),
    'matplotlib': ('https://matplotlib.org/', None),
    "monty": ("http://pythonhosted.org/monty/", None),
    "pymatgen": ("http://pymatgen.org/", None),
    'mayavi': ('http://docs.enthought.com/mayavi/mayavi', None),
}

# If true, Sphinx will warn about all references where the target cannot be found.
# Default is False. You can activate this mode temporarily using the -n command-line switch.
#nitpicky = True

# A string of reStructuredText that will be included at the end of every source file that is read.
# This is the right place to add substitutions that should be available in every file.
with open("links.rst", "rt") as fh:
    rst_epilog = fh.read()

# http://www.sphinx-doc.org/en/stable/ext/extlinks.html#confval-extlinks
# :abivar:`ecut`
#ABINIT_DOCS_URL =
#extlinks = {'
#    "abivar" : (ABINIT_DOC_ULRS + '/abinit/%s', "")
#    api_url' : (settings.BASE_URL + '%s', settings.BASE_URL)
#}

autodoc_member_order = "bysource"

#'members', 'undoc-members', 'private-members', 'special-members', 'inherited-members' and 'show-inheritance'.
#autodoc_default_flags = ["show-inheritance", "inherited-members", "special-members"]

# From https://sphinxcontrib-bibtex.readthedocs.io/en/latest/usage.html#custom-formatting-sorting-and-labelling
# pybtex provides a very powerful way to create and register new styles, using setuptools entry points,
# as documented here: http://docs.pybtex.org/api/plugins.html

#from pybtex.style.formatting.unsrt import Style as UnsrtStyle
#from pybtex.style.template import toplevel # ... and anything else needed
#from pybtex.plugin import register_plugin

#class MyStyle(UnsrtStyle):
#    def format_label(self, entry):
#        print("hello")
#        return "APA"
#
#    #def format_XXX(self, e):
#    #    template = toplevel [
#    #        # etc.
#    #    ]
#    #    return template.format_data(e)

#register_plugin('pybtex.style.formatting', 'mystyle', MyStyle)

# This is for releases http://releases.readthedocs.io/en/latest/usage.html
releases_github_path = "abinit/abipy"
