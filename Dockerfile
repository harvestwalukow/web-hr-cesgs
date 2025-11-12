FROM python:3.10

# Install system dependencies required to build dlib
RUN apt-get update && apt-get install -y \
	cmake \
	build-essential \
	libboost-all-dev \
	libssl-dev \
	libffi-dev \
	python3-dev \
	&& rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

ADD https://github.com/ufoscout/docker-compose-wait/releases/download/2.7.3/wait /wait
RUN chmod +x /wait

RUN chmod +x ./entry.sh

CMD /wait && ./entry.sh

