# syntax=docker/dockerfile:1

FROM gcr.io/google.com/cloudsdktool/google-cloud-cli:464.0.0

WORKDIR app

COPY app/requirements.txt requirements.txt

RUN pip3 install -r requirements.txt

COPY app/. .

CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]
