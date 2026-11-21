# Neighbour-removed protocol sweep (e5-base). GPU0: A,B concurrently; GPU1: C,D once its replicates finish.
source env.sh; X=../data/exclude_near_dev_tune_095.parquet
run() { CUDA_VISIBLE_DEVICES=$1 $PY train_mt.py --model intfloat/multilingual-e5-base --run-id $2 --exclude $X --bs 32 --epochs 6 ${@:3} > ../logs/$2.log 2>&1 && CUDA_VISIBLE_DEVICES=$1 $PY embed_ft.py --run-id $2 > ../logs/post_$2.log 2>&1 && CUDA_VISIBLE_DEVICES=$1 $PY probe_knn.py --emb ft_$2 --exclude $X >> ../logs/post_$2.log 2>&1; }
run 0 P_lr2e5 --lr 2e-5 & run 0 P_lr5e5 --lr 5e-5 &
while pgrep -f "[r]un-id e5b_s17|[r]un-id e5b_s23e3|[e]mbed_ft.py --run-id e5b_s|[p]robe_knn.py --emb ft_e5b_s" >/dev/null; do sleep 10; done
run 1 P_lr3e5 --lr 3e-5 & run 1 P_lr3e5_noreg --lr 3e-5 --label-smoothing 0 --aug 0 &
CUDA_VISIBLE_DEVICES="" $PY tfidf_protocol.py $X > ../logs/protocol_tfidf.log 2>&1 &
CUDA_VISIBLE_DEVICES=1 $PY probe_knn.py --emb e5-small --exclude $X --tag _P > ../logs/knn_P.log 2>&1 &
wait
