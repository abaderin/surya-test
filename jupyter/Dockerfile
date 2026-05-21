FROM surya-test:base
RUN groupadd --gid 1000 jupyter \
    && useradd --uid 1000 --gid 1000 --create-home --home-dir /home/jupyter --shell /bin/bash jupyter
RUN uv pip install --system jupyter
RUN mkdir /home/jupyter/workspace
WORKDIR /home/jupyter/workspace
USER jupyter
EXPOSE 18888
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=18888", "--no-browser"]
