#!/bin/bash

docker exec -it atlas-spark-master \
/opt/spark/bin/spark-submit \
--master spark://spark-master:7077 \
"$@"