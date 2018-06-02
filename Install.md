nstall the Node-Red Fallback Skill

For the Mark 1
sudo apt-get install libssl-dev libffi-dev
sudo msm install https://github.com/JarbasAl/fallback-node-red
cd opt
source venvs/mycroft-core/bin/activate
cd mycroft
cd skills
cd fallback-node-red.rdelange
pip install -r requirements.txt
deactivate
sudo service mycroft-skills restart

For Picroft
sudo apt-get install libssl-dev libffi-dev
sudo msm install https://github.com/JarbasAl/fallback-node-red
sudo service mycroft-skills restart

For desktop Mycroft dev installations
cd /home/username/mycroft-core/msm
./msm install https://github.com/JarbasAl/fallback-node-red
./msm update
