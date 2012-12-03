# coding=utf8

from distutils.core import setup
from flubber import __version__


setup(name             = "flubber",
      version          = __version__,
      author           = "Saúl Ibarra Corretgé",
      author_email     = "saghul@gmail.com",
      url              = "http://github.com/saghul/flubber", # not yet
      description      = "Cooperative multitasking and i/o for Python",
      long_description = open("README.rst").read(),
      packages         = ["flubber", "flubber.core", "flubber.ext", "flubber.green"],
      platforms        = ["POSIX", "Microsoft Windows"],
      classifiers      = [
          "Development Status :: 4 - Beta",
          "Intended Audience :: Developers",
          "License :: OSI Approved :: MIT License",
          "Operating System :: POSIX",
          "Operating System :: Microsoft :: Windows",
          "Programming Language :: Python",
          "Programming Language :: Python :: 2",
          "Programming Language :: Python :: 2.6",
          "Programming Language :: Python :: 2.7",
          #"Programming Language :: Python :: 3",
          #"Programming Language :: Python :: 3.0",
          #"Programming Language :: Python :: 3.1",
          #"Programming Language :: Python :: 3.2"
      ],
     )

