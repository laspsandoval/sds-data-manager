#!/bin/bash

echo "Generating database requirements file"
poetry export -f requirements.txt --with layer-database -o lambda_layer/database/requirements.txt --without-urls

echo "Generating processing requirements file"
poetry export -f requirements.txt --with layer-processing -o lambda_layer/processing/requirements.txt --without-urls

echo "Generating spice requirements file"
poetry export -f requirements.txt --with layer-spice -o lambda_layer/spice/requirements.txt --without-urls

touch test.txt

echo "Requirements files generated successfully."