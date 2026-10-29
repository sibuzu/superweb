import {getStore} from '@netlify/blobs';
import {handleFavorites} from '../lib/shared-favorites.mjs';
import protocol from '../../favorites-sync.js';

export default async request => {
  if (!protocol.allowedOrigin(request.headers.get('Origin'), request.url)) return new Response(JSON.stringify({error: '此入口的收藏僅儲存在瀏覽器。'}), {status: 403, headers: {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store'}});
  try {
    return await handleFavorites(request, getStore({name: 'hft-shared-favorites', consistency: 'strong'}));
  } catch (_) {
    return new Response(JSON.stringify({error: '雲端暫時無法使用，收藏會保留在本機等待重試。'}), {status: 503, headers: {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store'}});
  }
};
