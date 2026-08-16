#!/bin/bash


me="$(basename "$0")"
maxlen="$2"     # Longitud máxima de la cuerda antes de dividir en líneas
lines="$1"      # Es mejor si maxlen% lines es 0
tmp_dir="/tmp"

function only_me_or_exit {
	# Asegúrese de que solo se esté ejecutando 1 instancia
	touch "$1"
	read lastPID < "$1" 	# Si lastPID no es nulo y existe un proceso con ese pid, salir 	[ ! -z "$lastPID" -a -d /proc/$lastPID ] && { echo "Ya se está ejecutando una instancia de $me con pid $lastPID." ; exit 1 ; } 	# else - Guardar pid en el archivo de bloqueo y continuar 	echo $$ > "$1"
}

function exit_only_me {
	rm "$pidfile"
	exit
}

function otherinfo_func {
	# Obtener el tiempo actual y total de la canción
	iCurrentTime="$(audtool --current-song-output-length)"
	iTotalTime="$(audtool --current-song-length)"
	echo "${iCurrentTime}/${iTotalTime}"
}

function join_maxlen_func {
	# 2 strings - $1 y $2 - no pasar $maxlen de caracteres
    # pero la primera cuerda debe acortarse, no la 2da.
	dots=""
	[ ${#1} -gt $((maxlen - ${#2})) ] && dots="..."
	echo "${1:0:((maxlen - ${#dots} - ${#2}))}$dots $2"
}

function lines_func {
	string="$1"
	for (( ; lines > 1 ; lines-- ))
	do
		length=${#string}
		for (( fwd=$((length/lines)) , bwd=$((length/lines)) ; bwd >= 0 ; fwd++ , bwd-- ))
		do
			if [[ "${string:$fwd:1}" = " " ]]
			then
				echo "${string:0:$fwd}"
				string="${string:$((fwd + 1))}"
				break
			fi
			if [[ "${string:$bwd:1}" = " " ]]
			then
				echo "${string:0:$bwd}"
				string="${string:$((bwd + 1))}"
				break
			fi
			#~ "${string:$bwd:1}"
			#~ wordlength
		done
	done
	echo "$string"
}

# Solo se tiene que ejecutar 1 sola instancia
pidfile="$tmp_dir/${me}_pid"
only_me_or_exit "$pidfile"

if pidof audacious >/dev/null
then

	status="$(audtool --playback-status)"
    infostring="$(audtool --current-song)"	
    
	case "$status" in
		"playing") 
		#echo ""
		lines_func " $(join_maxlen_func "$infostring" "$(otherinfo_func)")"
		exit_only_me
		;;
		"paused") 
		#echo ""
		lines_func " $(join_maxlen_func "$infostring" "$(otherinfo_func)")"
		exit_only_me
		;;
	esac
	
fi

echo # no icon for uptime?
exit_only_me
