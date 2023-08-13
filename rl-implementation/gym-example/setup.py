from setuptools import setup

setup(name='gym_example',
      version='0.0.2',
      install_requires=['gym==0.16.0','requests','kubernetes==v12.0.1','pint','pyyaml']  # And any other dependencies foo needs
      #dependency_links=['http://github.com/kubernetes-client/repo/tarball/master#egg=python-12.0.0-snapshot']
)
