import spotipy
import spotipy.util as sputil
import numpy as np
import pandas as pd
import os

from spotipy.oauth2 import SpotifyClientCredentials
from sklearn.preprocessing import StandardScaler

AUDIO_FEATURES = ['danceability', 'energy', 'acousticness', 'instrumentalness', 'key', 'liveness', 'loudness', 'speechiness', 'tempo', 'time_signature', 'valence']

def chunk(l, chunk_sz=50): 
    for i in range(0, len(l), chunk_sz):  
        yield l[i:i + chunk_sz]

class MusicRecommender():
    def __init__(self):
        client_credentials_manager = SpotifyClientCredentials(client_id=os.environ['CLIENT_ID'], client_secret=os.environ['CLIENT_SECRET'])
        self.sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

    def related_artists(self, artist_id):
        res = self.sp.artist_related_artists(artist_id)
        return [a['id'] for a in res['artists']]
    
    def recommend(self, song_name, n = 1):
        # Convert song name to artist ID
        res = self.sp.search(q=song_name)
        if not res['tracks']['items']:
            print(f'Failed to find matching song for song name: {song_name}')
            return None
        q_track = res['tracks']['items'][0]
        t_id = q_track['id']
        artist_id = q_track['artists'][0]['id']
        print('Got artist name: ' + q_track['artists'][0]['name'])

        related = self.related_artists(artist_id)

        # Collect songs from related
        songs = []
        for rid in related:
            songs += [x['id'] for x in self.sp.artist_top_tracks(rid)['tracks']]

        # Get features from related
        feat_list = []
        for c in chunk(songs):
            feat = self.sp.audio_features(c)
            feat_list += [x for x in feat if x is not None]

        # Convert to DF
        df = pd.DataFrame.from_records(feat_list)
        feat_df = df[AUDIO_FEATURES]

        # Z-normalize input
        scaler = StandardScaler()
        scaled = scaler.fit_transform(feat_df.values)

        # Get original track's audio features
        base_feat_dict = self.sp.audio_features(t_id)[0]
        x_in = np.array([base_feat_dict[feat] for feat in AUDIO_FEATURES]).reshape((1, -1))
        x_scaled = scaler.transform(x_in)

        # Find NNs
        best_idxs = np.argsort(np.sum(np.square(scaled - x_scaled), axis=1))

        q_feat = [float(x) for x in x_in.reshape((-1,))]
        output = []
        # TODO: use tracks() instead of track() each time
        for best_idx in best_idxs[:n]:
            best_id = df.loc[best_idx]['id']
            best_info = self.sp.track(best_id)
            best_feats = [float(x) for x in feat_df.values[best_idx, :].reshape((-1,))]

            print(f'Found best result at {best_idx} ({best_id})')
            print(f'https://open.spotify.com/track/{best_id}')
            output.append({
                'features': {AUDIO_FEATURES[i]: best_feats[i] for i in range(len(AUDIO_FEATURES))},
                'id': best_id,
                'name': best_info['name'],
                'album': best_info['album'],
                'url': f'https://open.spotify.com/track/{best_id}'
            })
        return {
            'input': {
                'features': {AUDIO_FEATURES[i]: q_feat[i] for i in range(len(AUDIO_FEATURES))},
                'name': q_track['name'],
                'album': q_track['album']
            },
            'output': output
        }

