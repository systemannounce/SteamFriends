import steam

if __name__ == '__main__':
    app = steam.SteamFriends()
    app.delete_non_friends()
