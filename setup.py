# coding=utf8

from distutils.core import setup
from evergreen import __version__


setup(name             = "evergreen",
      version          = __version__,
      author           = "Saúl Ibarra Corretgé",
      author_email     = "saghul@gmail.com",
      url              = "http://github.com/saghul/evergreen",
      description      = "Cooperative multitasking and i/o for Python",
      long_description = open("README.rst").read(),
      packages         = ["evergreen", "evergreen.ext", "evergreen.futures", "evergreen.lib"],
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

