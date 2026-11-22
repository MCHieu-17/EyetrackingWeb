# k6 summary

scenario: samples

- http_req_blocked: p(90)=0.014, p(95)=0.017, p(99)=0.159, avg=0.014, min=0.002, med=0.011, max=0.173
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- iterations: count=233.000, rate=22.913
- http_req_waiting: avg=16.691, min=6.088, med=14.936, max=55.829, p(90)=24.323, p(95)=24.961, p(99)=44.639
- http_req_failed: rate=0.000
- vus: min=5.000, max=5.000
- http_req_sending: med=0.040, max=0.300, p(90)=0.052, p(95)=0.057, p(99)=0.105, avg=0.042, min=0.007
- http_req_duration: avg=16.830, min=6.172, med=15.140, max=55.980, p(90)=24.475, p(95)=25.151, p(99)=44.778
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.116, avg=0.002, min=0.000, med=0.000, max=0.118
- http_req_duration{expected_response:true}: avg=16.830, min=6.172, med=15.140, max=55.980, p(90)=24.475, p(95)=25.151, p(99)=44.778
- http_req_receiving: med=0.090, max=0.347, p(90)=0.146, p(95)=0.168, p(99)=0.289, avg=0.096, min=0.033
