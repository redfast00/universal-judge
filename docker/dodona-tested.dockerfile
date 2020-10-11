FROM python:3.9.0-slim-buster

# First, install all necessary packages for running things.
RUN mkdir -p /usr/share/man/man1/
RUN apt-get update && apt-get install -y --no-install-recommends default-jdk haskell-platform gcc-8 nodejs dos2unix curl zip unzip
ENV SDKMAN_DIR /usr/local/sdkman
RUN curl -s "https://get.sdkman.io?rcupdate=false" | bash
RUN chmod a+x "$SDKMAN_DIR/bin/sdkman-init.sh"
RUN /bin/bash -c "source \"$SDKMAN_DIR/bin/sdkman-init.sh\" && sdk install kotlin"
ENV PATH $SDKMAN_DIR/candidates/kotlin/current/bin:$PATH

RUN pip install jsonschema psutil mako pydantic==1.4 toml typing_inspect pylint
RUN cabal update && cabal install aeson --global --force-reinstalls

RUN chmod 711 /mnt

RUN useradd -m runner
RUN mkdir /home/runner/workdir && chown runner:runner /home/runner/workdir

USER runner
WORKDIR /home/runner/workdir

COPY main.sh /main.sh

