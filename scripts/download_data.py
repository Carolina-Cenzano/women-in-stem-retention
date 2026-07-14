"""Fetches the NSCG 2023 public use file into ../data/.

The extracted survey CSV is about 140 MB, which is over GitHub's file size
limit, so the raw data is not committed to this repository. Run this once
before prepare_data.py.

Survey page:
https://ncses.nsf.gov/explore-data/microdata/national-survey-college-graduates
"""

import os
import urllib.request
import zipfile

URL = "https://ncses.nsf.gov/822/assets/0/files/college_grads_2023.zip"
DEST = os.path.join(os.path.dirname(__file__), "..", "data")


def main():
    os.makedirs(DEST, exist_ok=True)
    marker = os.path.join(DEST, "pcg23Public", "epcg23.csv")
    if os.path.exists(marker):
        print("already downloaded:", marker)
        return
    archive = os.path.join(DEST, "college_grads_2023.zip")
    if not os.path.exists(archive):
        print("downloading", URL, "(about 61 MB)")
        urllib.request.urlretrieve(URL, archive)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(DEST)
    print("extracted to", os.path.join(DEST, "pcg23Public"))


if __name__ == "__main__":
    main()
