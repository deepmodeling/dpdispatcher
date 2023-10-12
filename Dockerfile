FROM python:3.12 AS compile-image

RUN python -m venv /opt/venv
# Make sure we use the virtualenv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /data/dpdispatcher
COPY ./ ./
RUN pip install .[bohrium]

FROM python:3.12 AS build-image
COPY --from=compile-image /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
CMD ["/bin/bash"]
