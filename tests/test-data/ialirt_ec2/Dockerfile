# This code is used to Dockerize test_app.py. The workflow is as follows:
# 1. Check that you are not already logged in by running `cat ~/.docker/config.json` and ensuring that neither
# Nexus registry URL is in the list of logged in registries.
# 2. Run `docker login docker-registry.pdmz.lasp.colorado.edu` (you will be prompted for your WebIAM username and password).
# Your `~/.docker/config.json` file should now contain a reference to the registry url.
# 3. `docker build -t my-image-primary:dev --rm . --no-cache`
# 4. `docker tag my-image-primary:dev docker-registry.pdmz.lasp.colorado.edu/ialirt/my-image-primary:dev`
# 5. `docker push docker-registry.pdmz.lasp.colorado.edu/ialirt/my-image-primary:dev`

# To run and test locally:
# 1. `docker build -t my-image-<primary or secondary> --rm .`
# 2. `docker run -it --privileged -e AWS_PROFILE=<profile> -v /dev/macfuse0:/dev/macfuse0
# -v ~/.aws:/root/.aws -p <port>:<port> my-image-<primary or secondary>`
# 3. http://localhost:<port> to see the "Hello World." message.
# http://localhost:<port>/list to see the list of files in the mounted S3 bucket.

FROM python:3.10
COPY . /app

# Set the working directory in the container
WORKDIR /app

# Install Flask
RUN pip install flask

# Non-interactive frontend for apt-get
ARG DEBIAN_FRONTEND=noninteractive

# Install dependencies and mountpoint-s3
RUN apt-get update && \
    apt-get install -y sudo wget fuse apt-utils && \
    wget https://s3.amazonaws.com/mountpoint-s3-release/latest/x86_64/mount-s3.deb && \
    sudo apt-get install -y ./mount-s3.deb && \
    rm ./mount-s3.deb && \
    # Create the /mnt/s3 directory
    mkdir -p /mnt/s3

# Copy the scripts into the container
COPY mount_s3.sh /app/mount_s3.sh
COPY start_flask.sh /app/start_flask.sh
COPY entrypoint.sh /app/entrypoint.sh

# Make the scripts executable
RUN chmod +x /app/mount_s3.sh /app/start_flask.sh /app/entrypoint.sh

# Make port 8080 available to the world outside this container
# Note: The port number is changed from 8080 to 80 for the secondary system.
EXPOSE 80

# Set the AWS region
ENV AWS_REGION us-west-2

# Command to run the entrypoint script
CMD ["/app/entrypoint.sh"]
