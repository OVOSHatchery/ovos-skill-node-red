Install the Node-Red Fallback Skill

For the Mark 1
sudo apt-get install libssl-dev libffi-dev
sudo msm install https://github.com/JarbasAl/fallback-node-red
sudo service mycroft-skills restart

MARK1 VIRTUAL ENV:
cd opt
source venvs/mycroft-core/bin/activate
deactivate

For Picroft
sudo apt-get install libssl-dev libffi-dev
sudo msm install https://github.com/JarbasAl/fallback-node-red
sudo service mycroft-skills restart

For desktop Mycroft dev installations
cd /home/username/mycroft-core/msm
./msm install https://github.com/JarbasAl/fallback-node-red
./msm update
