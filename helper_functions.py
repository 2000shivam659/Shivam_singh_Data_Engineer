
import os
import boto3
import zipfile
import requests
import pandas as pd
from logger import log
from xml.etree import ElementTree as ET


def download(url, download_path, filename):

    file = ""
    log.info("Downloading the xml file.")
    try:
        # Getting the content of the file
        response = requests.get(url)

        markup_file_ext = ["xml", "html"]

        if (
            filename.split(".")[-1] in markup_file_ext
            and filename.split(".")[-1] not in response.text
        ):
            return file

        # Checking if the requests got a correct response
        if response.ok:
            # Creating directories in the given download path if not exists
            if not os.path.exists(download_path):
                os.makedirs(download_path)
            # Creating the filepath for downloading xml file
            file = os.path.join(download_path, filename)

            # Creating the xml file at the path with the given file name
            with open(file, "wb") as f:
                f.write(response.content)

                log.info("xml file downloaded")
        else:
            # Logging if the download of the xml file fails
            log.error("Error while downloading the xml file")
    except Exception as e:
        # Logging if the download of the xml file fails
        log.error(f"Error occurred - {str(e)}")

    return file


def parse_source_xml(xml_file):

    try:
        log.info("Loading the xml file.")
        # Loading the xml file content
        xmlparse = ET.parse(xml_file)

        log.info("Parsing the xml file.")
        # Getting the required xml root (<result>)
        root = xmlparse.getroot()[1]
        # Getting all the doc tag elements
        docs = root.findall("doc")

        log.info("Traversing all the doc elements.")
        # Traversing through all the doc tag elements
        for doc in docs:

            log.info("Extracting the file type")
            # Extracting file type of the doc
            file_type = doc.find(".//str[@name='file_type']")

            # Checking if the file type of the doc 'DLTINS'
            if file_type.text == "DLTINS":

                log.info("Match found for file type DLTINS")

                # Extracting the File name and download link from the xml
                log.info("Extracting the file name")
                file_name = doc.find(".//str[@name='file_name']").text

                log.info("Extracting the file download link")
                download_link = doc.find(".//str[@name='download_link']").text

                # Breaking out of the loop since we got the first file download
                # link with file type 'DLTINS'
                break
        else:
            log.info("Match not found for file type DLTINS")
            # Returning from the function if not matches of file type found
            return

        return file_name, download_link

    except Exception as e:
        log.error(f"Error occurred - {str(e)}")


def unzip_file(zipped_file, uncompressed_file_path):

    try:
        log.info("Extracting the compressed file")
        with zipfile.ZipFile(zipped_file, "r") as zip_ref:
            zip_ref.extractall(uncompressed_file_path)

        log.info("Compressed file extracted")

        return True
    except Exception as e:
        log.error(f"Error occurred while extracting - {str(e)}")
        return False


def create_csv(xml_file, csv_path):

    try:
        # Checking if the path exists or not
        if not os.path.exists(csv_path):
            # Creating the path
            log.info("Creating CSV file path")
            os.makedirs(csv_path)

        # Extracting the csv file name from xml file
        csv_fname = xml_file.split(os.sep)[-1].split(".")[0] + ".csv"

        # Creating csv file path
        csv_file = os.path.join(csv_path, csv_fname)

        log.info("Loading the xml file")
        # Creating xml file itertor
        xml_iter = ET.iterparse(xml_file, events=("start",))

        csv_columns = [
            "FinInstrmGnlAttrbts.Id",
            "FinInstrmGnlAttrbts.FullNm",
            "FinInstrmGnlAttrbts.ClssfctnTp",
            "FinInstrmGnlAttrbts.CmmdtyDerivInd",
            "FinInstrmGnlAttrbts.NtnlCcy",
            "Issr",
        ]

        # Creating empty dataframe with the required column names
        df = pd.DataFrame(columns=csv_columns)

        # List to store the extacted data
        extracted_data = []

        log.info("Parsing the xml file...")
        log.info("Extracting the required data from xml")
        # Traversing the xml data
        for event, element in xml_iter:

            # Checking for start of the tags
            if event == "start":

                # Checking for TermntdRcrd tag in which the required data is
                if "TermntdRcrd" in element.tag:

                    # Dictionary to store require data in single element
                    data = {}

                    # List of the required tags (FinInstrmGnlAttrbts, Issr)
                    reqd_elements = [
                        (elem.tag, elem)
                        for elem in element
                        if "FinInstrmGnlAttrbts" in elem.tag or "Issr" in elem.tag
                    ]

                    # Traversing through the required tags
                    for tag, elem in reqd_elements:

                        if "FinInstrmGnlAttrbts" in tag:

                            # Traversing through the child elements of
                            # FinInstrmGnlAttrbts element
                            for child in elem:

                                # Adding the extrcated data in the dictionary
                                if "Id" in child.tag:
                                    data[csv_columns[0]] = child.text
                                elif "FullNm" in child.tag:
                                    data[csv_columns[1]] = child.text
                                elif "ClssfctnTp" in child.tag:
                                    data[csv_columns[2]] = child.text
                                elif "CmmdtyDerivInd" in child.tag:
                                    data[csv_columns[3]] = child.text
                                elif "NtnlCcy" in child.tag:
                                    data[csv_columns[4]] = child.text

                        # Extracting Issr Tag value
                        else:
                            data[csv_columns[5]] = child.text

                    # Appending the single element extracted data in the list
                    extracted_data.append(data)

        log.info("All the required data extracted from xml file")

        # Appending the extracted data in the data frame
        df = pd.DataFrame(extracted_data,columns=csv_columns)


        log.info("Dropping empty rows")
        # Removes empty rows from the dataframe
        df.dropna(inplace=True)

        log.info("Creating the CSV file")
        # Creates csv file from the dataframe
        df.to_csv(csv_file, index=False)

        # returning the csv file path
        return csv_file

    except Exception as e:
        log.error(f"Error occurred while extracting - {str(e)}")


def aws_s3_upload(file, region_name, aws_access_key_id, aws_secret_access_key, bucket_name):

    try:
        # Extracting the file name from the path
        filename_in_s3 = file.split(os.sep)[-1]

        log.info("Creating S3 resource object")
        # Connecting to S3 bucket with boto3
        s3 = boto3.resource(
            service_name="s3",
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        log.info("Uploading the file to s3 bucket")
        # Uploads the file to the s3 bucket
        s3.Bucket(bucket_name).upload_file(Filename=file, Key=filename_in_s3)

        log.info("File uploaded successfully to s3 bucket")

        # returning True for successful upload
        return True
    except Exception as e:
        log.error(f"Error occurred while extracting - {str(e)}")
