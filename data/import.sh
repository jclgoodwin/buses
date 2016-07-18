#!/bin/bash

# Usage:
#
#     cd data
#     ./import.sh username password
#
# Where 'username' and 'password' are your username and password for the
# Traveline National Dataset FTP server

trap "echo Exited!; exit;" SIGINT SIGTERM

if [ "$(ps -e | grep -c import.sh)" -gt 2 ]; then
    echo "An import appears to be running already"
    exit 0
fi

USERNAME=$1
PASSWORD=$2
REGIONS=(NCSD EA W EM Y NW S WM SW SE NE L) # roughly in ascending size order

function import_csv {
    # name of a zip archive:
    zip=$1
    # fragment of a Django management command name:
    cmd=$2
    # name of a CSV file contained in the zip archive:
    csv=$3

    tail -n +2 "$csv" > "previous/$csv" || touch "previous/$csv"
    unzip -oq "$zip" "$csv"
    diff -h "previous/$csv" "$csv" | grep '^> ' | sed 's/^> //' | ../../manage.py "import_$cmd"
}

mkdir -p NPTG/previous NaPTAN TNDS
. ../env/bin/activate


cd NPTG
nptg_old=$(shasum nptg.ashx\?format=csv)
wget -qN http://naptan.app.dft.gov.uk/datarequest/nptg.ashx?format=csv
nptg_new=$(shasum nptg.ashx\?format=csv)

if [[ $nptg_old != $nptg_new ]]; then
    echo "NPTG"
    echo "  Importing regions"
    import_csv nptg.ashx\?format=csv regions Regions.csv
    echo "  Importing areas"
    import_csv nptg.ashx\?format=csv areas AdminAreas.csv
    echo "  Importing districts"
    import_csv nptg.ashx\?format=csv districts Districts.csv
    echo "  Importing localities"
    import_csv nptg.ashx\?format=csv localities Localities.csv
    echo "  Importing locality hierarchy"
    import_csv nptg.ashx\?format=csv locality_hierarchy LocalityHierarchy.csv
    # ../../manage.py update_index busstops.Locality --remove
fi


cd ../NaPTAN
naptan_old=$(shasum naptan.zip)
../../manage.py update_naptan
naptan_new=$(shasum naptan.zip)

if [[ "$naptan_old" != "$naptan_new" ]]; then
    echo "NaPTAN"
    unzip -oq naptan.zip
fi

if [ -f *csv.zip ]; then
    for file in *csv.zip; do
        unzip -oq "$file" Stops.csv StopAreas.csv StopsInArea.csv
        echo " $file"
        echo "  Stops"
        ../../manage.py import_stops < Stops.csv || exit
        echo "  Stop areas"
        ../../manage.py import_stop_areas < StopAreas.csv || exit
    done
    for file in *csv.zip; do
        echo " $file"
        echo "  Stops in area"
        ../../manage.py import_stops_in_area < StopsInArea.csv || exit
        rm "$file"
    done
fi


cd ..

noc_old=$(ls -l NOC_DB.csv)
wget -qN http://mytraveline.info/NOC/NOC_DB.csv
wget -qN www.travelinedata.org.uk/noc/api/1.0/nocrecords.xml
noc_new=$(ls -l NOC_DB.csv)
if [[ $noc_old != $noc_new ]]; then
    ../manage.py import_operators < NOC_DB.csv
    ../manage.py correct_operator_regions
    ../manage.py import_operator_contacts < nocrecords.xml
    ../manage.py import_scotch_operator_contacts < NOC_DB.csv
#    ../manage.py update_index busstops.Operator --remove
fi

if [[ $USERNAME == '' || $PASSWORD == '' ]]; then
   echo 'TNDS username and/or password not supplied :('
   exit 1
fi

cd TNDS
date=$(date +%Y-%m-%d)
for region in "${REGIONS[@]}"; do
    region_old=$(ls -l $region.zip)
    wget -qN --user="$USERNAME" --password="$PASSWORD" ftp://ftp.tnds.basemap.co.uk/$region.zip
    region_new=$(ls -l $region.zip)
    if [[ $region_old != $region_new ]]; then
        # updated_services=1
        ../../manage.py import_services $region.zip
    fi
done
# [ $updated_services ] && ../../manage.py update_index --remove
