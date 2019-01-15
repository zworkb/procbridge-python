from setuptools import setup, find_packages

setup(
  name='procbridge',
  packages=find_packages('src'),
  package_dir={'': 'src'},
  # packages=['procbridge'],
  version='1.0.2',
  description='A lightweight socket-based IPC (Inter-Process Communication) protocol.',
  author='Gong Zhang',
  author_email='zhanggong@me.com',
  url='https://github.com/gongzhang/proc-bridge',
  download_url='https://github.com/gongzhang/proc-bridge/archive/1.0.tar.gz',
  keywords=['ipc', 'socket', 'communication', 'process', 'json'],
  classifiers=[],
)
