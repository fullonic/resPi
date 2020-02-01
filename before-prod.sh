echo ------- moving venv out -------
mv venv/ ../
mv .git/ ../
mv build/ ../
mv dist/ ../


echo ------- removing pycache and logs -------
sudo rm -rf __pycache__
sudo rm -rf logs

echo ------- create new logs folder -------
mkdir logs

cd ../

echo ------- sending to Pi -------
scp -r resPI/ pi@192.168.4.1:/home/pi

echo ------- moving venv -------
mv venv/ resPI/
mv .git/ resPI/
mv build/ resPI/
mv dist/ resPI/
echo ------- Done -------
