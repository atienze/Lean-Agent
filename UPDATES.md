9/7
- Using Typer object for CLI interface. 
- upon "lean init" a config file will be created
    - there exists a function in paths.py that will check the creation of the config file for 
    status of initalization
LEFT OFF:
- building the config.json schema and decided on using pydantic for object validation.

9/15
- config file set up with pydantic. 
    - created default_config()
        - blank LeanConfig() object returned
    - created save_config()
        - writes config object to .lean/config.json path
    - created merge_overrides
        - takes LeanConfig obj and a dict of changed config values
        - merges together with default/existing config
        - returns the updated LeanConfig object
    - created init_project()
        - merges default config with potential overrides
        - writes to .lean/config.json w/ save_config()
LEFT OFF:
- config schema and cli init function should be finished. will need to do small testing segment then continue to next portion of project.
    

