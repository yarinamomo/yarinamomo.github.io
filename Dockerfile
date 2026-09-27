# Local preview with the same Jekyll version and plugins that GitHub Pages uses.
FROM ruby:3.3

RUN gem install github-pages webrick --no-document

WORKDIR /srv/jekyll

# 4000: the site, 35729: live reload
EXPOSE 4000 35729

# --force_polling: file-change events do not cross a Windows bind mount, so poll for changes instead.
CMD ["jekyll", "serve", "--host", "0.0.0.0", "--livereload", "--force_polling"]
