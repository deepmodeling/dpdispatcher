FROM python:3.11

WORKDIR /data/dpdispatcher
COPY ./ ./
RUN pip install .[cloudserver]
