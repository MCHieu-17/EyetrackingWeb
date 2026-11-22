# k6 summary

scenario: replay

- http_req_connecting: p(90)=0.000, p(95)=0.005, p(99)=0.073, avg=0.005, min=0.000, med=0.000, max=0.091
- http_req_duration: avg=14.725, min=4.325, med=16.629, max=23.755, p(90)=19.214, p(95)=20.584, p(99)=23.120
- http_req_blocked: max=0.122, p(90)=0.019, p(95)=0.045, p(99)=0.107, avg=0.017, min=0.003, med=0.011
- http_req_receiving: med=0.204, max=1.108, p(90)=0.407, p(95)=0.453, p(99)=0.977, avg=0.257, min=0.081
- http_req_duration{expected_response:true}: p(99)=23.120, avg=14.725, min=4.325, med=16.629, max=23.755, p(90)=19.214, p(95)=20.584
- http_req_sending: avg=0.045, min=0.012, med=0.043, max=0.153, p(90)=0.050, p(95)=0.065, p(99)=0.135
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- vus: min=1.000, max=1.000
- http_req_waiting: avg=14.423, min=4.210, med=16.359, max=23.505, p(90)=18.837, p(95)=19.476, p(99)=22.699
- http_req_failed: rate=0.000
- iterations: count=20.000, rate=4.632
