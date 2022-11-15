FROM python:3.8

WORKDIR /data/dpdispatcher
COPY ./ ./
RUN pip install .
