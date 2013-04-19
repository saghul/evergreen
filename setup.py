# coding=utf8

import re
from distutils.core import setup


def get_version():
    return re.search(r"""__version__\s+=\s+(?P<quote>['"])(?P<version>.+?)(?P=quote)""", open('evergreen/__init__.py').read()).group('version')

setup(name             = "evergreen",
      version          = get_version(),
      author           = "Saúl Ibarra Corretgé",
      author_email     = "saghul@gmail.com",
      url              = "http://github.com/saghul/evergreen",
      description      = "Cooperative multitasking and i/o for Python",
      long_description = open("README.rst").read(),
      packages         = ["evergreen", "evergreen.ext", "evergreen.futures", "evergreen.io", "evergreen.lib"],
      install_requires = [i.strip() for i in open("requirements.txt").readlines() if i.strip()],
      platforms        = ["POSIX", "Microsoft Windows"],
      classifiers      = [
          "Development Status :: 3 - Alpha",
          "Intended Audience :: Developers",
          "License :: OSI Approved :: MIT License",
          "Operating System :: POSIX",
          "Operating System :: Microsoft :: Windows",
          "Programming Language :: Python",
          "Programming Language :: Python :: 2",
          "Programming Language :: Python :: 2.6",
          "Programming Language :: Python :: 2.7",
          "Programming Language :: Python :: 3",
          "Programming Language :: Python :: 3.2"
          "Programming Language :: Python :: 3.3"
      ],
     )

