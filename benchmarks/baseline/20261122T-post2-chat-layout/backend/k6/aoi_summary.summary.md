# k6 summary

scenario: aoi_summary

- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_duration: p(95)=34.163, p(99)=36.730, avg=25.198, min=10.372, med=27.112, max=37.060, p(90)=33.613
- iterations: count=90.000, rate=8.846
- http_req_waiting: avg=25.064, min=10.289, med=26.918, max=36.942, p(90)=33.471, p(95)=34.050, p(99)=36.596
- http_req_failed: rate=0.000
- http_req_receiving: max=0.393, p(90)=0.109, p(95)=0.128, p(99)=0.242, avg=0.079, min=0.035, med=0.065
- http_req_sending: p(90)=0.067, p(95)=0.079, p(99)=0.154, avg=0.055, min=0.013, med=0.052, max=0.174
- http_req_connecting: avg=0.002, min=0.000, med=0.000, max=0.086, p(90)=0.000, p(95)=0.000, p(99)=0.074
- http_req_blocked: avg=0.014, min=0.003, med=0.011, max=0.122, p(90)=0.016, p(95)=0.028, p(99)=0.101
- http_req_duration{expected_response:true}: avg=25.198, min=10.372, med=27.112, max=37.060, p(90)=33.613, p(95)=34.163, p(99)=36.730
- vus: min=2.000, max=2.000
