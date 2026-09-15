"""Import all BDD scenarios from .feature files for pytest discovery."""
from pytest_bdd import scenarios

# Discover all .feature files in the features directory
scenarios("features")
