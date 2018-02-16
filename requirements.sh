SOURCE="${BASH_SOURCE[0]}"
DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
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
        echo "$parsed" >> "$DIR/mycroft/configuration/sys.conf"
        value=$( jq -r "$key" "$DIR/mycroft/configuration/sys.conf" )
        if [[ "${value}" != "null" ]] ;  then
            rm -rf $DIR/mycroft/configuration/sys.conf
            echo "$value"
            return
        fi
    fi
  done
  echo "$default"
}


# Determine the platform
mycroft_platform="$(get_config_value '.enclosure.platform' 'null')"
if [[ "${mycroft_platform}" == "null" ]] ; then
   if [[ "$(hostname)" == "picroft" ]] ; then
      mycroft_platform="picroft"
   elif [[ "$(hostname)" =~ "mark_1" ]] ; then
      mycroft_platform="mycroft_mark_1"
   fi
fi

if [[ "${mycroft_platform}" == "null" ]] ; then
    sudo apt-get install libssl-dev libffi-dev
else
    apt-get install libssl-dev libffi-dev
fi