FROM python:3.8

WORKDIR /data/dpdispatcher
ADD requirements.txt ./
RUN pip install -r requirements.txt
COPY ./ ./
RUN pip install .
