SOURCE="${BASH_SOURCE[0]}"
DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
# TODO get mycroft core root path
SYSTEM_CONFIG="$DIR/mycroft/configuration/mycroft.conf"

function get_config_value() {
  key="$1"
  default="$2"
  value="null"
  for file in ~/.mycroft/mycroft.conf /etc/mycroft/mycroft.conf $SYSTEM_CONFIG;   do
    if [[ -r $file ]] ; then
        # remove comments in config for jq to work
        # assume they may be preceded by whitespace, but nothing else
        parsed="$( sed 's:^\s*//.*$::g' $file )"
        echo "$parsed" >> "$DIR/sys.conf"
        value=$( jq -r "$key" "$DIR/sys.conf" )
        if [[ "${value}" != "null" ]] ;  then
            rm -rf $DIR/sys.conf
            echo "$value"
            return
        fi
    fi
  done
  echo "$default"
}


raspi="$(get_config_value '.enclosure.platform' 'linux')"

if [[ ${raspi} == 'picroft' ]] || [[ ${raspi} == 'mark_1' ]] ; then
    bash <(curl -sL https://raw.githubusercontent.com/node-red/raspbian-deb-package/master/resources/update-nodejs-and-nodered)
else
    curl -sL https://deb.nodesource.com/setup_9.x | sudo -E bash -
    sudo apt-get install -y nodejs
    sudo npm install -g --unsafe-perm node-red
fi

sudo apt-get install libssl-dev
