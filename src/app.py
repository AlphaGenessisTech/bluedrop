import json
import logging
from io import BytesIO
from PIL import Image
import os
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def extract_thermistors(bucket: str, key: str):
    s3_client = boto3.client("s3")

    # Read log file from S3
    file_byte_string = s3_client.get_object(Bucket=bucket, Key=key)["Body"].read()
    log_text = file_byte_string.decode("utf-8")
    logger.info(f"Log file contents: {log_text}")

    # Extract thermistor measurements from log file
    measurements = []
    for line in log_text.split("\n"):
        if "thermistor" in line:
            data = line.split()
            measurements.append(
                {"timestamp": data[0], "thermistor": int(data[1]), "temperature": float(data[2])}
            )
    logger.info(f"Thermistor measurements: {measurements}")

    # Write measurements to JSON file
    device_id = os.path.splitext(os.path.basename(key))[0].split("-")[0]
    output_key = f"{device_id}-thermistors.json"
    output_body = json.dumps(measurements).encode("utf-8")
    s3_client.put_object(Bucket=bucket, Key=output_key, Body=output_body)
    logger.info(f"Wrote thermistor measurements to S3 object: s3://{bucket}/{output_key}")


def lambda_handler(event, context):
    logger.info(f"event: {event}")
    logger.info(f"context: {context}")
    
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]

    bluedrop_bucket = "cp-bluedrop-image-bucket"
    bluedrop_name, bluedrop_ext = os.path.splitext(key)
    bluedrop_key = f"{bluedrop_name}_bluedrop{bluedrop_ext}"

    logger.info(f"Bucket name: {bucket}, file name: {key}, Bluedrop Bucket name: {bluedrop_bucket}, file name: {bluedrop_key}")

    s3_client = boto3.client('s3')

    # Load and open image from S3
    file_byte_string = s3_client.get_object(Bucket=bucket, Key=key)['Body'].read()
    img = Image.open(BytesIO(file_byte_string))
    logger.info(f"Size before compression: {img.size}")

    # Generate bluedrop
    img.bluedrop((500,500), Image.ANTIALIAS)
    logger.info(f"Size after compression: {img.size}")

    # Dump and save image to S3
    buffer = BytesIO()
    img.save(buffer, "JPEG")
    buffer.seek(0)
    
    sent_data = s3_client.put_object(Bucket=bluedrop_bucket, Key=bluedrop_key, Body=buffer)

    if sent_data['ResponseMetadata']['HTTPStatusCode'] != 200:
        raise Exception('Failed to upload image {} to bucket {}'.format(key, bucket))

    # Extract thermistor measurements from log file and save to S3
    extract_thermistors(bucket, key)

    return event
