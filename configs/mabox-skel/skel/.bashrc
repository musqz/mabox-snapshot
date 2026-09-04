#
# ~/.bashrc
#
# Local addition to mabox-skel (not part of the upstream sync from
# git.maboxlinux.org/Mabox/mabox-skel -- that tree has never shipped a
# .bashrc, see mabox_snapshot/seed.py). A future wholesale re-sync of
# configs/mabox-skel/skel/ from upstream will silently drop this file
# unless upstream adds an equivalent -- carry it forward by hand.

[[ $- != *i* ]] && return

export HISTSIZE=5000
export HISTFILESIZE=5000
export PATH=$HOME/bin:$PATH

colors() {
	local fgc bgc vals seq0

	printf "Color escapes are %s\n" '\e[${value};...;${value}m'
	printf "Values 30..37 are \e[33mforeground colors\e[m\n"
	printf "Values 40..47 are \e[43mbackground colors\e[m\n"
	printf "Value  1 gives a  \e[1mbold-faced look\e[m\n\n"

	# foreground colors
	for fgc in {30..37}; do
		# background colors
		for bgc in {40..47}; do
			fgc=${fgc#37} # white
			bgc=${bgc#40} # black

			vals="${fgc:+$fgc;}${bgc}"
			vals=${vals%%;}

			seq0="${vals:+\e[${vals}m}"
			printf "  %-9s" "${seq0:-(default)}"
			printf " ${seq0}TEXT\e[m"
			printf " \e[${vals:+${vals+$vals;}}1mBOLD\e[m"
		done
		echo; echo
	done
}

[ -r /usr/share/bash-completion/bash_completion ] && . /usr/share/bash-completion/bash_completion

# Change the window title of X terminals
case ${TERM} in
	xterm*|rxvt*|Eterm*|aterm|kterm|gnome*|interix|konsole*)
		PROMPT_COMMAND='history -a;history -n;echo -ne "\033]0;${USER}@${HOSTNAME%%.*}:${PWD/#$HOME/\~}\007"'
		;;
	screen*)
		PROMPT_COMMAND='echo -ne "\033_${USER}@${HOSTNAME%%.*}:${PWD/#$HOME/\~}\033\\"'
		;;
esac

use_color=true

# Set colorful PS1 only on colorful terminals.
# dircolors --print-database uses its own built-in database
# instead of using /etc/DIR_COLORS.  Try to use the external file
# first to take advantage of user additions.  Use internal bash
# globbing instead of external grep binary.
safe_term=${TERM//[^[:alnum:]]/?}   # sanitize TERM
match_lhs=""
[[ -f ~/.dir_colors   ]] && match_lhs="${match_lhs}$(<~/.dir_colors)"
[[ -f /etc/DIR_COLORS ]] && match_lhs="${match_lhs}$(</etc/DIR_COLORS)"
[[ -z ${match_lhs}    ]] \
	&& type -P dircolors >/dev/null \
	&& match_lhs=$(dircolors --print-database)
[[ $'\n'${match_lhs} == *$'\n'"TERM "${safe_term}* ]] && use_color=true

if ${use_color} ; then
	# Enable colors for ls, etc.  Prefer ~/.dir_colors #64489
	if type -P dircolors >/dev/null ; then
		if [[ -f ~/.dir_colors ]] ; then
			eval "$(dircolors -b ~/.dir_colors)"
		elif [[ -f /etc/DIR_COLORS ]] ; then
			eval "$(dircolors -b /etc/DIR_COLORS)"
		fi
	fi

	if [[ ${EUID} == 0 ]] ; then
		PS1='\[\033[01;31m\][\h\[\033[01;36m\] \W\[\033[01;31m\]]\$\[\033[00m\] '
	else
		PS1="\[$(tput bold)\]\[\033[38;5;2m\]\u\[$(tput sgr0)\]\[\033[38;5;11m\]@\[$(tput sgr0)\]\[\033[38;5;6m\]\h\[$(tput sgr0)\] \[$(tput sgr0)\]\[$(tput bold)\]\[\033[38;5;11m\]\w\[$(tput sgr0)\] \[$(tput sgr0)\]\[$(tput bold)\]\[\033[38;5;13m\]\\$\[$(tput sgr0)\] \[$(tput sgr0)\]"
	fi

	alias ls='ls --color=auto'
	alias grep='grep --colour=auto'
	alias egrep='egrep --colour=auto'
	alias fgrep='fgrep --colour=auto'
else
	if [[ ${EUID} == 0 ]] ; then
		# show root@ when we don't have colors
		PS1='\u@\h \W \$ '
	else
		PS1='\u@\h \w \$ '
	fi
fi

unset use_color safe_term match_lhs

alias cat='cat -v'
alias cp="cp -i"                          # confirm before overwriting something
alias df='df -h'                          # human-readable sizes
alias free='free -m'                      # show sizes in MB
alias ll='ls -lah'
alias ..='cd ..'
alias ...='cd ../../'
alias more=less
alias mc='. /usr/lib/mc/mc-wrapper.sh'


complete -cf sudo

# Bash won't get SIGWINCH if another process is in the foreground.
# Enable checkwinsize so that bash will check the terminal size when
# it regains control.  #65623
# http://cnswww.cns.cwru.edu/~chet/bash/FAQ (E11)
shopt -s checkwinsize

shopt -s expand_aliases

# Enable history appending instead of overwriting.  #139609
shopt -s histappend
shopt -s cmdhist
export HISTCONTROL=ignoreboth:erasedups

#
# # ex - archive extractor
# # usage: ex <file>
ex ()
{
  if [ -f "$1" ] ; then
    case "$1" in
      *.tar.bz2)   tar xjf "$1"   ;;
      *.tar.gz)    tar xzf "$1"   ;;
      *.bz2)       bunzip2 "$1"   ;;
      *.rar)       unrar x "$1"     ;;
      *.gz)        gunzip "$1"    ;;
      *.tar)       tar xf "$1"    ;;
      *.tbz2)      tar xjf "$1"   ;;
      *.tgz)       tar xzf "$1"   ;;
      *.zip)       unzip "$1"     ;;
      *.Z)         uncompress "$1";;
      *.7z)        7z x "$1"      ;;
      *)           echo "'$1' cannot be extracted via ex()" ;;
    esac
  else
    echo "'$1' is not a valid file"
  fi
}

# Colorized man using less
man() {
    LESS_TERMCAP_md=$'\e[01;31m' \
    LESS_TERMCAP_me=$'\e[0m' \
    LESS_TERMCAP_se=$'\e[0m' \
    LESS_TERMCAP_so=$'\e[01;44;33m' \
    LESS_TERMCAP_ue=$'\e[0m' \
    LESS_TERMCAP_us=$'\e[01;32m' \
    command man "$@"
}

# Theme.sh
export THEME_HISTFILE=~/.theme_history
[ -e "$THEME_HISTFILE" ] && theme.sh "$(theme.sh -l|tail -n1)"
alias th='theme.sh -i2 && fastfetch'

ROOT_TERMINAL_THEME="red-alert"
SSH_TERMINAL_THEME="mellow-purple"

su() {
	(
		INHIBIT_THEME_HIST=1 theme.sh "${ROOT_TERMINAL_THEME}"
		restored=0
		trap 'theme.sh "$(theme.sh -l|tail -n1)"; restored=1' INT
		env su "$@"
		[ "$restored" = 0 ] && theme.sh "$(theme.sh -l|tail -n1)"
	)
}

sudo() {
	(
		pid=$(exec sh -c 'echo "$PPID"')

		# If the command takes less than .2s, don't change the theme.
		# We could also just match on 'su' and ignore everything else,
		# but this also accomodates other long running commands
		# like 'sudo sleep 5s'. Modify to taste.

		(
				sleep .2s
				ps -p "$pid" > /dev/null && INHIBIT_THEME_HIST=1 theme.sh "${ROOT_TERMINAL_THEME}"
		) &
		disown

		restored=0
		trap 'theme.sh "$(theme.sh -l|tail -n1)"; restored=1' INT
		env sudo "$@"
		[ "$restored" = 0 ] && theme.sh "$(theme.sh -l|tail -n1)"
	)
}

ssh() {
	(
		INHIBIT_THEME_HIST=1 theme.sh "${SSH_TERMINAL_THEME}"
		restored=0
		trap 'theme.sh "$(theme.sh -l|tail -n1)"; restored=1' INT
		env ssh "$@"
		[ "$restored" = 0 ] && theme.sh "$(theme.sh -l|tail -n1)"
	)
}

# Todo.txt
export TODOTXT_DEFAULT_ACTION=ls
alias t='mabox-todo.sh'
