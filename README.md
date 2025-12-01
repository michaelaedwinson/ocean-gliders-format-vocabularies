This repo validates yaml files for use with the [Ocean Gliders OG1 format](https://oceangliderscommunity.github.io/OG-format-user-manual/OG_Format.html)

It reads in yaml files from 'yaml/draft_yaml' and runs a series of checks against the [NERC vocab server](http://vocab.nerc.ac.uk/). It makes some simple in-place corrections and inferences (e.g. linked manufacturer of a sensor) and applies those to the yaml. Yaml that pass the tests are written out to `yaml/validated_yaml`. Any failed tests/warnings/recommendations are written to the log file for action.
