# Filo - A Discord FFXIV hunting bot

Filo is a Discord bot created for the FFXIV hunting community. Its primary purpose is to automatically relay hunts found via the XivHunt client to dedicated Discord channels. This is an alternative to utilizing the actual XivHunt client or Horus' desktop notifications and aims to help ensure everyone has a fair chance to get to hunts in-game without relying entirely on manual relays.

Additionally, it supports an interactive scouting assistance feature, allowing members of a dedicated scouting channel to easily add flags for found hunts to a dedicated list in prepation for a hunt train, FFXIV account verification (as a means to combat abuse), and more!

As of today, Filo has relayed over 1,750 A-Rank hunts, 4,000 S-Ranks, and organized over 100 hunt trains on Mateus' Hunt Discord alone!

## Features
* Automated relays for ARR, HW, SB, and ShB A/S rank hunt openings, finds and/or deaths, powered by XivHunt and Horus
* FFXIV account verification powered by XivApi
* Hunt status lookup
* Hunt train scouting tracker (temporarily unavailable)
* Hunt train progress tracker (temporarily unavailable)

## Planned features
* Special fate tracking
* Early spawn warnings for timed S-Ranks


# Documentation
```
FFXIV:
  iam                  Link your FFXIV character to Filo
  verify               Verify an account linked with the f.iam command
  whoami               Get information on your linked FFXIV character
  whois                Get the specified discord users FFXIV account
Hunts:
  info                 Return information on the specified hunt target
  notify               Adds a role to mention when hunts are found in this ch...
  status               Retrieve the status of the specified hunt target
  sub                  Subscribe the channel to hunt events
  sub-all              Subscribe the channel to hunt events on ALL Crystal DC...
  sub-clear            Clear all enabled subscriptions for this channel
  sub-list             List all enabled subscriptions for this channel
  train                Announces the start of a SB hunt train on the specifie...
  train-cancel         Blows up the train. Boom.
  unsub                Subscribe the channel to hunt events
Misc:
  stats                Get some miscellaneous bot statistics
Scouting:
  add                  Add a hunt entry to the scouting list
  addsniped            Mark a hunt as sniped
  cancel               Cancel a previously initialized scouting session
  end                  Close an active scouting session and log the completio...
  logs                 Display the scouting action logs
  refresh              Delete and repost the scouting tracker as the most rec...
  restore              Restore a previously concluded hunt
  scoreboard           Hunt leaders - run f.help scoreboard for more information
  start                Start a new scouting session
Settings:
  reload               Reload settings
  set-verified         Change the role given to verified members
  set-verified-message Change the message displayed to users after they have ...
  settings             List a guild setting or settings
​No Category:
  help                 Shows this message
  
Type f.help command for more info on a command.
You can also type f.help category for more info on a category.
```
Note: Filobot's commands are executed with the `f.` prefix.


## Hunt tracking
![](https://i.imgur.com/UuQm5FI.png)

Channels can be subscribed to up to two primary channels:
1. A-Ranks
2. S-Ranks

Each primary channel has 3 sub-channels:
1. **Finds** - Announces when a hunt has been found and relayed by the XivHunt client and Horus. Most commonly used with Deaths.
2. **Deaths** - Announces when a hunt has been killed. If also subscribed to Finds and a found hunt was announced, that message will instead be edited to show when the relayed hunt was killed.
3. **Openings** - Less commonly used, this announces when a hunt has "opened" or reached its maximum spawn window

To subscribe to these channels, a server administrator should run the `f.sub` command in the desired channel:
```
f.sub <world> <category> [conditions="FINDS, DEATHS"]

Subscribe the channel to hunt events
Allowed categories: SHB_A, SHB_S, SB_A, SB_S, HW_A, HW_S, ARR_A, ARR_S
Allowed conditions: FINDS, DEATHS, OPENINGS
```

For example, to subscribe a channel to **Shadowbringer S-Ranks** relays and death notifications on the world **Mateus**, you would run the following command:
`f.sub Mateus SHB_S`

Once that has been done, you may wish to set a Discord role to ping with these notifications with the `f.notify` command. For example, if you have members who wish to subscribe to S-Rank notifications in the **@S Ranks** role, you would run the following in the desired channel:
`f.notify @S Ranks`


## Account verification
![](https://i.imgur.com/yABYCKA.png)
To set up a verified role for your Discord server, run the `f.set-verified` command. For example:
`f.set-verified @✔️ verified`

You can also customize the message that displays after a member has verified their account with the `f.set-verified-message`.

Once this has been done, members can link their accounts with by running `f.iam World Firstname Lastname`. For example:
`f.iam Mateus Totomo Omo`

After this has been done, the user will be prompted to paste a verification code into their lodestone profile. Once they have done this and run `f.verify`, they will be given the configured verified role for your Discord server.

## Scouting
**Note: This feature has not been updated for Shadowbringers yet and is temporarily unavailable.**
Scouting sessions can be started with the `f.start` command.

![](https://i.imgur.com/gMKWTXj.png)

Once a session has started, Filo will ping everyone @here to let them know scouting for a train has begun. Because of this, and to prevent sniping/abuse, if you wish to start a scouting sessions on your server we recommend creating a private channel that only trusted scouters can access.

Hunts can be added to the scouting list with `f.add` as demonstrated above. If a hunt has been sniped, you can mark it as such with `f.addsniped`.

Once a train has concluded, you can end the scouting session with `f.end` - if you accidentally end the session too early, you can restore it with `f.restore`.