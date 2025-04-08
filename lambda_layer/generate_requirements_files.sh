#!/bin/bash

poetry export -f requirements.txt --with layer-database -o database/requirements.txt --without-urls
poetry export -f requirements.txt --with layer-processing -o processing/requirements.txt --without-urls
poetry export -f requirements.txt --with layer-spice -o spice/requirements.txt --without-urls

echo "Requirements files generated successfully."