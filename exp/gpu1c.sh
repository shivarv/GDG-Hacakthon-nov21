source env.sh; export CUDA_VISIBLE_DEVICES=1
while [ ! -f ../results/knn_ft_e5b_long.json ]; do sleep 15; done
$PY train_mt.py --model intfloat/multilingual-e5-base --run-id e5b_xl --seed 23 --bs 32 --lr 4e-5 --epochs 12 > ../logs/e5b_xl.log 2>&1
$PY embed_ft.py --run-id e5b_xl > ../logs/post_e5b_xl.log 2>&1 && $PY probe_knn.py --emb ft_e5b_xl >> ../logs/post_e5b_xl.log 2>&1
