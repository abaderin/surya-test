FROM surya-test:base
RUN groupadd --gid 1000 jupyter \
    && useradd --uid 1000 --gid 1000 --create-home --home-dir /home/jupyter --shell /bin/bash jupyter
RUN usermod -aG sudo jupyter
RUN uv pip install --system jupyter
RUN uv pip install --system pymupdf djvulibre-python rich
USER jupyter
WORKDIR /home/jupyter
EXPOSE 18888
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=18888", "--no-browser"]
