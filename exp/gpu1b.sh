source env.sh; export CUDA_VISIBLE_DEVICES=1
while [ $(ls ../runs/e5s_s*/DONE 2>/dev/null | wc -l) -lt 3 ]; do sleep 15; done
$PY embed_frozen.py --model intfloat/multilingual-e5-base --name e5-base > ../logs/emb_e5b.log 2>&1
$PY probe_knn.py --emb e5-base > ../logs/knn_e5b.log 2>&1 &
$PY train_mt.py --model intfloat/multilingual-e5-base --run-id e5b_long --seed 17 --bs 32 --lr 4e-5 --epochs 8 > ../logs/e5b_long.log 2>&1
