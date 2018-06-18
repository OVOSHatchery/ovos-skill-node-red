Install the Node-Red Fallback Skill

For the Mark 1
sudo apt-get install libssl-dev libffi-dev
sudo msm install https://github.com/JarbasAl/fallback-node-red.git
sudo ufw allow 6789/tcp (this will open the port in the firewall, needed if you run nodered on other server)
sudo service mycroft-skills restart

MARK1 VIRTUAL ENV:
cd opt
source venvs/mycroft-core/bin/activate
deactivate

For Picroft
sudo apt-get install libssl-dev libffi-dev
sudo msm install https://github.com/JarbasAl/fallback-node-red.git
sudo service mycroft-skills restart

For desktop Mycroft dev installations
cd /home/username/mycroft-core/msm
./msm install https://github.com/JarbasAl/fallback-node-red.git
./msm update
