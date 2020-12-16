# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

# get version from __version__ variable in shipstation_integration/__init__.py
from shipstation_integration import __version__ as version

setup(
	name='shipstation_integration',
	version=version,
	description='Shipstation integration for ERPNext',
	author='Parsimony LLC',
	author_email='developers@parsimony.com',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
