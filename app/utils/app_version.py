apps = [
        {
            "app_name": "BHT-EMR-API",
            "app_version": "v5.3.3"
        },
        {
            "app_name": "HIS-Core",
            "app_version": "v2024.Q3.R7"
        },
        {
            "app_name": "HIS-Core-release",
            "app_version": "v2024.Q3.R7"
        },
    ]

def getTag(app_dir):
    for app in apps:
        if  app["app_name"] in app_dir:
            return app["app_version"]
    return None

def generate_git_url(directory_path):
    base_url = "3000/gitea/"
    # Split the directory path by "/"
    path_parts = directory_path.split("/")
    # Get the last part of the path as the repository name
    repository_name = path_parts[-1]
    # Append ".git" to the repository name
    repository_name_with_extension = repository_name + ".git"
    # Concatenate the base URL, repository name, and ".git" extension
    git_url = base_url + repository_name_with_extension
    return git_url

def check_versions(version_list):
    found_versions = set()
    
    for version in version_list:
        for app in apps:
            if app['app_version'] == version:
                found_versions.add(version)
                break
    
    return len(found_versions) == len(apps)
