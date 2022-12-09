#!/bin/bash
WYZE_EMAIL=youremail
WYZE_PASSWORD=yourpassword
WYZE_TOTP=TOTP
Garmin_username=youremail
Garmin_password=yourpassword
export WYZE_EMAIL
export WYZE_PASSWORD
export WYZE_TOTP
cd /path_to_yourscript/
python3 ./scale.py > ./test
cat ./test | awk -F\<wyze_sdk.ScaleRecord '{print $2}' | awk -F'[ |/}]'  '{printf $5$7$9$11$13$15$17$34$38$40$49}' > ./test5
cp ./wyze.csv ./wyze.1.csv
awk -F, '{$8=substr($8, 1, 10); ts= $8-631065600; printf "Data,0,weight_scale,timestamp,";printf "%.0f",ts; print",s,weight,"($11*0.45359237)",kg,percent_fat,"$3",\045,percent_hydration,"$6",\045,muscle_mass,"$10",kg,physique_rating,"$4",,basal_met,"$2",kcal/day,visceral_fat_rating,"$5",,bone_mass,"$7",kg,metabolic_age,"$9",years"}' ./test5 >> ./wyze.1.csv
md5sum ./wyze.1.csv | awk '{print $1,"./wyze.last.csv"}' > ./cksum.txt
#echo `cat ./wyze.1.csv`
Datavalid=$(awk -F',' 'END {print $NF}' ./wyze.1.csv)
if [ "$Datavalid" = "years" ]; then
echo "File is correct."
else
echo "File is not correct."
exit 0
fi
if md5sum -c ./cksum.txt; then
echo "no new measurment"
exit 0
else
java -jar /path_to_the_tool/FitCSVTool.jar -c ./wyze.1.csv ./wyze.fit
echo "fit file created"
gupload -u $Garmin_username -p $Garmin_password  -v 1 ./wyze.fit
echo "file uploaded"
mv ./wyze.1.csv ./wyze.last.csv
fi
rm ./test
rm ./test5
exit 0
