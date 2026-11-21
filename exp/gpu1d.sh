source env.sh; export CUDA_VISIBLE_DEVICES=1
for spec in "e5b_s17:17:4" "e5b_s23e3:23:3"; do IFS=: read rid seed ep <<< "$spec"
  ( $PY train_mt.py --model intfloat/multilingual-e5-base --run-id $rid --seed $seed --bs 32 --lr 3e-5 --epochs $ep > ../logs/$rid.log 2>&1 && $PY embed_ft.py --run-id $rid > ../logs/post_$rid.log 2>&1 && $PY probe_knn.py --emb ft_$rid >> ../logs/post_$rid.log 2>&1 ) &
done; wait
