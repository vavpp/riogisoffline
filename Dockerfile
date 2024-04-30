FROM qgis/qgis:latest

ENV QGIS_IN_CI 1

COPY . /app

WORKDIR /app

RUN python3 -m pip install -qr /app/test_riogisoffline/requirements.test.txt

ENTRYPOINT ["xvfb-run", "-a", "0"]

RUN python3 -m pytest test_riogisoffline/ --junit-xml=/app/report.xml

CMD ["cat", "/app/report.xml"]
