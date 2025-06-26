# Use the official Jekyll image
FROM jekyll/jekyll:4

# install webrick
RUN gem install webrick

# Set working directory inside the container
WORKDIR /srv/jekyll

# Expose the default port
EXPOSE 4000

# Run the development server on container start
CMD ["jekyll", "serve", "--host", "0.0.0.0", "--livereload"]
