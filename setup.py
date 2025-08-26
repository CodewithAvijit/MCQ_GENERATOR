from setuptools import find_packages,setup

setup(
    name="MCQ_GENERATOR",
    version='0.0.1',
    author='AVIJIT BHADRA',
    author_email='riyabha4566@gmail.com',
    install_requires=["langchain","google-genai","PyPDF2","python-dotenv","streamlit"],
    packages=find_packages()
)