# bash completion for mabox-snapshot
# Hand-written -- keep in sync with mabox_snapshot/cli.py's build_parser().

_mabox_snapshot_modes="preserving reset"
_mabox_snapshot_compressions="zstd xz lz4 lzo gzip"
_mabox_snapshot_profiles="full lean"
_mabox_snapshot_folders="Desktop Documents Downloads Music Pictures Videos Public Templates"
_mabox_snapshot_rule_actions="exclude include"
_mabox_snapshot_config_keys="workdir output_dir compression compression_level exclude_list
    exclude_folders kernel all_kernels demo_lang no_calamares skip_space_check
    change_threshold_mb encrypt profile checksums"

_mabox_snapshot_create() {
    case "$prev" in
        --compression)
            COMPREPLY=($(compgen -W "$_mabox_snapshot_compressions" -- "$cur")); return ;;
        --profile)
            COMPREPLY=($(compgen -W "$_mabox_snapshot_profiles" -- "$cur")); return ;;
        --exclude-folder)
            COMPREPLY=($(compgen -W "$_mabox_snapshot_folders" -- "$cur")); return ;;
        -w|--workdir|--output-dir)
            _filedir -d; return ;;
        --exclude-list)
            _filedir; return ;;
        --iso-name|--kernel|--compression-level|--change-threshold-mb)
            return ;;
    esac

    # mode is a positional argument (create {preserving,reset} [options]) --
    # offer it until one of the two values has actually been typed.
    local w mode_given=0
    for w in "${words[@]:2}"; do
        [[ "$w" == "preserving" || "$w" == "reset" ]] && mode_given=1
    done

    if [[ $mode_given -eq 0 && "$cur" != -* ]]; then
        COMPREPLY=($(compgen -W "$_mabox_snapshot_modes" -- "$cur"))
        return
    fi

    COMPREPLY=($(compgen -W "
        -w --workdir -o --skip-space-check --output-dir --iso-name
        --compression --compression-level --exclude-list --exclude-folder
        --kernel --all-kernels --dry-run --change-threshold-mb --encrypt
        --profile -n --no-checksums -h --help
    " -- "$cur"))
}

_mabox_snapshot_excludes() {
    local subcmd=${words[2]} subsubcmd=${words[3]}

    if [[ $cword -eq 2 ]]; then
        COMPREPLY=($(compgen -W "list edit reset folders add remove rules -h --help" -- "$cur"))
        return
    fi

    if [[ "$subcmd" != "rules" ]]; then
        return
    fi

    if [[ $cword -eq 3 ]]; then
        COMPREPLY=($(compgen -W "list add remove clear edit -h --help" -- "$cur"))
        return
    fi

    case "$subsubcmd" in
        add|remove)
            if [[ $cword -eq 4 ]]; then
                COMPREPLY=($(compgen -W "$_mabox_snapshot_rule_actions" -- "$cur"))
            fi
            ;;
        list)
            COMPREPLY=($(compgen -W "--compiled -h --help" -- "$cur"))
            ;;
    esac
}

_mabox_snapshot_config() {
    if [[ $cword -eq 2 ]]; then
        COMPREPLY=($(compgen -W "show path set -h --help" -- "$cur"))
        return
    fi

    if [[ "${words[2]}" == "set" && $cword -eq 3 ]]; then
        COMPREPLY=($(compgen -W "$_mabox_snapshot_config_keys" -- "$cur"))
    fi
}

_mabox_snapshot_packages() {
    if [[ $cword -eq 2 ]]; then
        COMPREPLY=($(compgen -W "list -h --help" -- "$cur"))
    elif [[ "${words[2]}" == "list" ]]; then
        COMPREPLY=($(compgen -W "--explicit --aur --local --all -h --help" -- "$cur"))
    fi
}

_mabox_snapshot_skel() {
    if [[ $cword -eq 2 ]]; then
        COMPREPLY=($(compgen -W "audit -h --help" -- "$cur"))
        return
    fi

    if [[ "${words[2]}" == "audit" ]]; then
        case "$prev" in
            --home) _filedir -d; return ;;
        esac
        COMPREPLY=($(compgen -W "--home --show-identical -h --help" -- "$cur"))
    fi
}

_mabox_snapshot() {
    local cur prev words cword
    _init_completion || return

    if [[ $cword -eq 1 ]]; then
        COMPREPLY=($(compgen -W "version doctor create config excludes packages skel -h --help" -- "$cur"))
        return
    fi

    case "${words[1]}" in
        create)   _mabox_snapshot_create ;;
        config)   _mabox_snapshot_config ;;
        excludes) _mabox_snapshot_excludes ;;
        packages) _mabox_snapshot_packages ;;
        skel)     _mabox_snapshot_skel ;;
        version|doctor)
            COMPREPLY=($(compgen -W "-h --help" -- "$cur"))
            ;;
    esac
} &&
    complete -F _mabox_snapshot mabox-snapshot
