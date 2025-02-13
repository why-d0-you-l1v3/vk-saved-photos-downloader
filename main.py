import json, os, requests, vk, vk_token
from sys import exit
from time import sleep
from urllib.parse import urlparse, unquote

token_file_name = "vk_token.py"
vk_api = vk.API(access_token=vk_token.token)

api_ver=5.199
max_count=1000  # max count of photos you may get at one request
api_requests_delay = 0.5    # to avoid captcha
photo_sizes = ["w", "z", "y", "x", "s", "r", "q", "p", "o", "m"]    # https://dev.vk.com/en/reference/objects/photo-sizes#Significance%20type%20for%20photos

link_result_file_name = "links_success.json"
link_invalid_file_name = "links_invalid.json"

download_folder_name = "Saved photos"
download_success_timeout = 2
download_fail_timeout = 30
download_max_retries = 10

def checkToken():
    if vk_token.token == "":
        print('Access token missing!')
        token_input = str(input("Paste it and press Enter: ")).strip()
        if token_input != "":
            with open(token_file_name, "r") as token_file:
                lines = token_file.readlines()
            with open(token_file_name, "w") as token_file:
                for line in lines:
                    if line.startswith("token ="):
                        token_file.write(f'token = "{token_input}"')
                    else:
                        token_file.write(line)
            print(f'Done! Token stored in "{token_file_name}" file, relaunch program.')
            exit(0)
        else:
            return checkToken()

# request for pictures count
def countRequest():
    count = vk_api.photos.get(v=api_ver, album_id="saved", count=0)["count"]
    sleep(api_requests_delay)
    return count

def getLinks(requests_count):
    result = []
    invalid = []
    offset = 0

    for x in range(0, requests_count):
        items = vk_api.photos.get(v=api_ver, album_id="saved", count=max_count, offset=offset)["items"]
        for obj in items:
            if obj.get("orig_photo") and "url" in obj["orig_photo"]:
                result.append({"id": obj["id"], "url": obj["orig_photo"]["url"], "warning": "", "downloaded": False})
            elif "orig_photo" not in obj and obj.get("sizes"):
                for size in photo_sizes:
                    for size_obj in obj["sizes"]:
                        if size_obj["type"] == size:
                            result.append({"id": obj["id"], "url": size_obj["url"], "warning": f"Photo {obj["id"]} hasn't original. Selected biggest size {size}.", "downloaded": False})
                            print(f"Photo {obj["id"]} hasn't original. Selected biggest size {size}.")
                            break
                    else:
                        continue
                    break
                else:
                    invalid.append(obj)
                    print(f"Photo {obj["id"]} hasn't original or sized copies. PHOTO WON'T BE DOWNLOADED!")
            else:
                invalid.append(obj)
                print(f"Photo {obj["id"]}: ERROR!")

        offset += max_count
        sleep(api_requests_delay)

    return result, invalid

def askUser(question, default="Y"):
    if default not in ["Y", "N"]:
        raise ValueError('Default must be "Y" or "N"')

    prompt = f"{question} [{'Y/n' if default == 'Y' else 'y/N'}]: "
    
    choice = input(prompt).strip().lower()
    
    if not choice:  # if enter pressed
        return default == "Y"
    elif choice in ["y", "yes", "д", "да"]:
        return True
    elif choice in ["n", "no", "н", "нет"]:
        return False
    else:
        print('Invalid input. Please enter "Y" or "N".')
        return askUser(question, default)

def getFileNameFromUrl(url):
    parsed_url = urlparse(url)
    filename_with_params = os.path.basename(parsed_url.path)
    filename = unquote(filename_with_params)
    return filename

def getFileExtensionFromUrl(url):
    filename = getFileNameFromUrl(url)
    extension = os.path.splitext(filename)[1]
    return extension

def downloader(links, saved_photos_count=0, use_orig_names=False):
    progress = 1
    warnings = 0
    errors = 0

    os.makedirs(download_folder_name, exist_ok=True)
    for link in links:
        if link["downloaded"]:
            print(f"Warning: photo {link["id"]} already downloaded!")
            warnings += 1
        else:
            retries = 0
            while retries < download_max_retries:
                try:
                    response = requests.get(link["url"])
                    response.raise_for_status()
                    if use_orig_names:
                        filename = getFileNameFromUrl(link["url"])
                    else:
                        filename = f"{link["id"]}{getFileExtensionFromUrl(link["url"])}"
                    file_path = os.path.join(download_folder_name, filename)
                    if os.path.isfile(file_path):
                        print(f"Warning: file {filename} already exists, rewriting!")
                        warnings +=1
                    with open(file_path, "wb") as file:
                        file.write(response.content)
                    link["downloaded"] = True
                    print(f"Photo {link["id"]} downloaded! File name: {filename}")
                    break

                except requests.RequestException as e:
                    retries += 1
                    print(f"Failed to download photo {link["id"]}. Attempt {retries}/{download_max_retries}. Error code: {e}")
                    if retries >= download_max_retries:
                        print(f"Error: failed to download photo {link["id"]} after {download_max_retries} attempts.")
                        errors +=1
                    else:
                        print(f"Next attempt in {download_fail_timeout} seconds, waiting...")
                        sleep(download_fail_timeout)

        if saved_photos_count != 0:
            print(f"{progress} of {saved_photos_count}", end=" ")
        if warnings > 0:
            print(f"warnings: {warnings}", end=" ")
        if errors > 0:
            print(f"errors: {errors}", end="")
        if saved_photos_count != 0 or warnings > 0 or errors > 0:
            print("")
        progress += 1

    return warnings, errors

def main():
    print("VK saved photos downloader\nhttps://github.com/why-d0-you-l1v3/vk-saved-photos-downloader\n")
    checkToken()
    saved_photos_count = countRequest()
    needed_requests_count = saved_photos_count // max_count + 1
    print(f"Saved photos: {saved_photos_count}")

    print("Getting download links...")
    result, invalid = getLinks(needed_requests_count)
    if (len(result) == saved_photos_count and len(invalid) == 0):
        print("Done!")
    print(f"Links got: {len(result)}\nFailed: {len(invalid)}")

    if askUser("Do you want to save image links (in json format)?", "N"):
        with open(link_result_file_name, "w") as file:
            json.dump(result, file, indent=4, ensure_ascii=False)
        with open(link_invalid_file_name, "w") as file:
            json.dump(invalid, file, indent=4, ensure_ascii=False)
        print(f"Done! Check {link_result_file_name} and {link_invalid_file_name} files.")
    if askUser("Use original file names?\nIt may rewrite images with same file names while downloading, if you have multiple same saved pictures.\nIf not, image id's will be used as file names.", "N"):
        use_orig_names = True
        print("Ok, using original file names.")
    else:
        use_orig_names = False
        print("Ok, using image id's as file names.")
    if askUser("Start downloading?", "Y"):
        warnings, errors = downloader(result, saved_photos_count, use_orig_names)

        if warnings == 0 and errors == 0:
            print("Done! ", end="")
        print("Download finished with", end="")
        if warnings == 0 and errors == 0:
            print("out errors", end="")
        if warnings > 0:
            print(f" {warnings} warnings", end="")
        if warnings > 0 and errors > 0:
            print(" and")
        if errors > 0:
            print(f"{errors} errors", end="")
        print(".")
        input("\nPress Enter to exit.")

    else:
        exit(0)

if __name__ == "__main__":
    main()